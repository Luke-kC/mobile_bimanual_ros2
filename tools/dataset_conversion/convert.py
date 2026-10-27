"""Offline rosbag2(MCAP) reader and deterministic diagnostic sample exporter.

Run from sourced ROS 2 Jazzy Python. This file imports ROS only inside the reader.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import yaml

try:
    from .alignment import Sample, PreparedStream, align, action_at, events_in_interval, grid, NS
    from .schema import load_schema
except ImportError:
    from alignment import Sample, PreparedStream, align, action_at, events_in_interval, grid, NS
    from schema import load_schema


def extract_trajectory(msg, joint):
    """Keep the complete trajectory event; never mistake it for a held setpoint.

    Point time_from_start is relative to trajectory start (header stamp when set).
    A zero header stamp means the controller chooses the start time.
    """
    names = list(msg.joint_names)
    if len(set(names)) != len(names) or names != [joint] or not msg.points:
        return None
    points = []
    last_offset = -1
    for pt in msg.points:
        t = int(pt.time_from_start.sec) * NS + int(pt.time_from_start.nanosec)
        if t < 0 or t <= last_offset or len(pt.positions) != 1:
            return None
        pos = float(pt.positions[0])
        if not math.isfinite(pos):
            return None
        points.append({"time_from_start_ns": t, "position": pos})
        last_offset = t
    header = msg.header.stamp
    return {"joint": joint, "header_stamp_ns": int(header.sec)*NS + int(header.nanosec),
            "points": points}


def extract_controller_state(msg, field, joint):
    names = list(msg.joint_names)
    if len(set(names)) != len(names) or joint not in names:
        return None
    index = names.index(joint)
    attr = {"controller_feedback": "feedback", "controller_reference": "reference",
            "controller_error": "error"}[field]
    positions = list(getattr(msg, attr).positions)
    if len(positions) != len(names):
        return None
    value = float(positions[index])
    return value if math.isfinite(value) else None


def extract(msg, field, joints=None, joint=None):
    if field == "joint_trajectory_event":
        return extract_trajectory(msg, joint)
    if field in {"controller_feedback", "controller_reference", "controller_error"}:
        return extract_controller_state(msg, field, joint)
    if field == "data":
        return msg.data
    if field == "data7":
        values = list(msg.data)
        return values if len(values) == 7 and all(math.isfinite(v) for v in values) else None
    if field == "named_position":
        # The actual joint name is authoritative, never its array index.
        if (len(msg.name) != len(msg.position) or
                len(set(msg.name)) != len(msg.name) or not joint):
            return None
        try:
            value = msg.position[msg.name.index(joint)]
        except ValueError:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return value if math.isfinite(value) else None
    if field == "named_positions":
        if len(msg.name) != len(msg.position) or len(set(msg.name)) != len(msg.name):
            return None
        mapping = dict(zip(msg.name, msg.position))
        values = [mapping.get(j) for j in joints]
        return values if all(v is not None and math.isfinite(v) for v in values) else None
    if field == "planar_twist":
        return [float(msg.linear.x), float(msg.angular.z)]
    if field == "twist_planar":
        return [float(msg.twist.twist.linear.x), float(msg.twist.twist.angular.z)]
    if field == "pose_planar":
        pos = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z))
        return [float(pos.x), float(pos.y), yaw]
    raise ValueError(f"Unsupported field {field}")


def read_rosbag_mcap(bag: Path, schema: dict, progress=None):
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except ImportError as exc:
        raise RuntimeError("Source ROS 2 Jazzy: rosbag2_py/rclpy required") from exc
    required_topics = {s["topic"] for s in schema["observations"].values()}
    desired = required_topics | {s[role] for s in schema["actions"].values() for role in ("requested", "authorized") if role in s}
    specs = defaultdict(list)
    for name, s in schema["observations"].items():
        specs[s["topic"]].append(("observations", name, s))
    for name, s in schema["actions"].items():
        for role in ("requested", "authorized"):
            if role not in s:
                continue
            specs[s[role]].append(("actions", f"{name}.{role}", s))
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"),
                rosbag2_py.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    for topic, entries in specs.items():
        if topic in types:
            for _, key, spec in entries:
                if types[topic] != spec["ros_type"]:
                    raise ValueError(f"Type mismatch for {topic}: {types[topic]} (expected {spec['ros_type']})")
    decoders = {name: get_message(types[name]) for name in desired & types.keys()}
    streams = defaultdict(list)
    counts = defaultdict(int)
    invalid = defaultdict(int)
    first_ns = last_ns = None
    while reader.has_next():
        topic, payload, t_ns = reader.read_next()
        if progress is not None:
            progress.tick()
        first_ns = t_ns if first_ns is None else min(first_ns, t_ns)
        last_ns = t_ns if last_ns is None else max(last_ns, t_ns)
        if topic not in decoders:
            continue
        counts[topic] += 1
        msg = deserialize_message(payload, decoders[topic])
        header_ns = None
        if hasattr(msg, "header"):
            stamp = msg.header.stamp
            header_ns = int(stamp.sec) * NS + int(stamp.nanosec)
        for _, key, s in specs[topic]:
            value = extract(msg, s["field"], s.get("joints"), s.get("joint"))
            if value is None:
                invalid[key] += 1
                continue
            streams[key].append(Sample(t_ns, value, header_ns))
    # rosbag2 may emit equal receive timestamps; latest at identical time wins.
    deduped = {}
    for key, samples in streams.items():
        merged = {s.timestamp_ns: s for s in samples}
        deduped[key] = sorted(merged.values(), key=lambda s: s.timestamp_ns)
    return deduped, dict(counts), dict(invalid), first_ns, last_ns


def build(schema: dict, streams: dict, start_ns: int, end_ns: int, *, profile: str, progress=None):
    if profile not in {"diagnostic", "training"}:
        raise ValueError("Unknown profile")
    timeline = grid(start_ns, end_ns, int(schema["dataset"]["fps"]))
    # Build timestamp indexes once, not on every sample/frame.
    streams = {key: PreparedStream.from_samples(samples) for key, samples in streams.items()}
    rows, rejections = [], defaultdict(int)
    mode_start = start_ns
    last_mode = None
    for idx, t_ns in enumerate(timeline):
        if progress is not None and (idx % 300 == 0 or idx + 1 == len(timeline)):
            progress(idx + 1, len(timeline))
        obs = {}
        for name, spec in schema["observations"].items():
            result = align(streams.get(name, []), t_ns, spec["alignment"],
                           max_gap_s=spec.get("max_gap_s", 0), max_age_s=spec.get("max_age_s", 0))
            obs[name] = result
        mode = obs.get("mode", {}).get("value") if obs.get("mode", {}).get("valid") else None
        if mode != last_mode:
            mode_start, last_mode = t_ns, mode
        commands = {}
        for name, spec in schema["actions"].items():
            for role in ("requested", "authorized"):
                if role not in spec:
                    continue
                key = f"{name}.{role}"
                if not spec.get("independent_of_mode", False) and mode != spec["mode"]:
                    commands[key] = {"valid": False, "reason": "inactive_mode"}
                elif spec["semantics"] == "event_target":
                    end = timeline[idx + 1] if idx + 1 < len(timeline) else t_ns + NS // int(schema["dataset"]["fps"])
                    events = events_in_interval(streams.get(key, []), t_ns, end)
                    commands[key] = {"valid": bool(events), "reason": "event" if events else "no_event", "events": [{"time_ns": e.timestamp_ns, "value": e.value} for e in events]}
                else:
                    commands[key] = action_at(streams.get(key, []), t_ns, semantics=spec["semantics"],
                                              mode_start_ns=mode_start, max_age_s=spec.get("max_age_s", 0))
        invalid_required = [name for name, spec in schema["observations"].items()
                            if spec.get("required") and not obs[name]["valid"]]
        if obs.get("pedestal_valid", {}).get("valid") and obs["pedestal_valid"]["value"] is False:
            invalid_required.append("pedestal_position_valid_false")
        if invalid_required:
            for name in invalid_required:
                rejections[name] += 1
        active = [k for k, spec in schema["actions"].items() if spec["mode"] == mode and not spec.get("independent_of_mode", False) and spec["semantics"] != "event_target"]
        missing_action = [f"{k}.authorized" for k in active if "authorized" in schema["actions"][k] and not commands[f"{k}.authorized"]["valid"]]
        row = {"index": idx, "timestamp": (t_ns - start_ns) / NS,
               "time_ns": t_ns, "mode": mode, "observations": obs,
               "commands": commands, "observation_valid": not invalid_required,
               "missing_active_actions": missing_action}
        if profile == "training" and (invalid_required or missing_action or not active):
            rejections["training_incomplete"] += 1
            continue
        rows.append(row)
    return rows, dict(rejections), len(timeline)


def convert(bag: Path, schema_path: Path, output: Path, *, profile: str, metadata: Path | None, progress=None):
    schema = load_schema(schema_path)
    if progress is not None:
        progress.stage("Reading MCAP")
    streams, counts, invalid, start, end = read_rosbag_mcap(bag, schema, progress=progress)
    if start is None or end is None:
        raise ValueError("Empty bag")
    missing = [name for name, spec in schema["observations"].items() if spec.get("required") and not streams.get(name)]
    if missing:
        raise ValueError(f"Required observation streams missing: {missing}")
    if progress is not None:
        progress.stage("Aligning 30 Hz samples")
    rows, rejected, total = build(schema, streams, start, end, profile=profile,
                                  progress=(progress.aligned if progress is not None else None))
    if not rows:
        raise ValueError(f"No valid rows for {profile} export; rejected={rejected}")
    if output.exists():
        raise FileExistsError(f"Output exists, refusing overwrite: {output}")
    if progress is not None:
        progress.stage("Writing outputs")
    output.mkdir(parents=True)
    (output / "samples.jsonl").write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
    meta = yaml.safe_load(metadata.read_text()) if metadata else {}
    report = {"format": "m19.6a_diagnostic_jsonl_v1", "profile": profile,
              "note": "NOT a LeRobotDataset: intermediate validated representation",
              "fps": schema["dataset"]["fps"], "episode": meta, "bag": str(bag),
              "first_ns": start, "last_ns": end, "grid_rows": total,
              "written_rows": len(rows), "rejections": rejected, "message_counts": counts,
              "invalid_decodes": invalid,
              "stream_counts": {k: len(v) for k, v in streams.items()},
              "observed_command_coverage": {name: len(streams.get(name, [])) for name in
                 [f"{a}.{r}" for a, spec in schema["actions"].items() for r in ("requested", "authorized") if r in spec]}}
    (output / "report.json").write_text(json.dumps(report, indent=2))
    (output / "schema.yaml").write_text(yaml.safe_dump(schema, sort_keys=False))
    return report


def main():
    from .batch import main as batch_main
    return batch_main()


if __name__ == "__main__":
    raise SystemExit(main())
