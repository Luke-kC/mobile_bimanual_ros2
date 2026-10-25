#!/usr/bin/env python3
"""Offline rosbag2 MCAP QA; requires ROS 2 Jazzy Python environment."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml


def validate(directory: Path) -> dict:
    metadata = yaml.safe_load((directory / "metadata.yaml").read_text())
    contract = yaml.safe_load((directory / "topics.yaml").read_text())["topics"]
    bag = directory / metadata["bag"]
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr", output_serialization_format="cdr"
        ),
    )
    types = {
        entry.name: entry.type for entry in reader.get_all_topics_and_types()
    }
    counts = Counter()
    stamps = defaultdict(list)
    joint_names = defaultdict(set)
    errors = []
    decoded_types = {}
    while reader.has_next():
        name, payload, timestamp_ns = reader.read_next()
        counts[name] += 1
        stamps[name].append(timestamp_ns)
        if contract.get(name, {}).get("joints"):
            try:
                msg_type = decoded_types.setdefault(
                    name, get_message(types[name])
                )
                msg = deserialize_message(payload, msg_type)
                joint_names[name].update(msg.name)
                if len(msg.name) != len(msg.position):
                    errors.append(
                        f"{name}: inconsistent joint name/position array lengths"
                    )
            except Exception as exc:
                errors.append(f"{name}: joint state decode failed: {exc}")
    present = [stamp for seq in stamps.values() for stamp in seq]
    duration = (max(present) - min(present)) / 1e9 if present else 0.0
    results = {}
    for name, spec in contract.items():
        number = counts[name]
        required = spec.get("required", False)
        issues = []
        if types.get(name) is not None and types[name] != spec["type"]:
            issues.append(f"type mismatch: {types[name]} != {spec['type']}")
        if required and not number:
            issues.append("no messages")
        # For short bags, count-based frequency is indicative, not a timing guarantee.
        if number > 1:
            times = stamps[name]
            if any(
                next_stamp < stamp
                for stamp, next_stamp in zip(times, times[1:])
            ):
                issues.append("recording timestamps regressed")
            span = (times[-1] - times[0]) / 1e9
            frequency = (number - 1) / span if span > 0 else None
            if (
                required
                and span > 0
                and spec.get("min_hz")
                and frequency < spec["min_hz"]
            ):
                issues.append(
                    f"rate {frequency:.2f} Hz below {spec['min_hz']} Hz"
                )
            if required and duration > 2.0:
                # Catch streams that disappear halfway through a trial.
                max_gap = max((b - a) / 1e9 for a, b in zip(times, times[1:]))
                if max_gap > max(1.0, duration * 0.25):
                    issues.append(f"large gap {max_gap:.2f} s")
                if (max(present) - times[-1]) / 1e9 > max(1.0, duration * 0.25):
                    issues.append("stream ended early")
        else:
            frequency = None
        required_joints = set(spec.get("joints", []))
        missing_joints = (
            sorted(required_joints - joint_names[name]) if number else []
        )
        if required and missing_joints:
            issues.append("missing joints: " + ", ".join(missing_joints))
        results[name] = {
            "required": required,
            "count": number,
            "approx_hz": round(frequency, 2) if frequency is not None else None,
            "status": "FAIL"
            if issues
            else ("PASS" if number else "NOT CONFIGURED"),
            "issues": issues,
        }
        if required:
            errors.extend(f"{name}: {issue}" for issue in issues)
    if duration < 0.5:
        errors.append(f"recording too short: {duration:.2f} s")
    if not (bag / "metadata.yaml").exists():
        errors.append("rosbag2 metadata.yaml missing")
    return {
        "episode_id": metadata["episode_id"],
        "duration_s": round(duration, 3),
        "total_messages": sum(counts.values()),
        "topics": results,
        "errors": errors,
        "passed": not errors,
        "limitations": [
            "Bag receive timestamps checked; message header and camera skew checks deferred to M19.5",
            "Command event coverage is not implied by topic availability",
            "No physical motion or task-success verification",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    args = parser.parse_args()
    try:
        report = validate(args.episode)
    except Exception as exc:
        report = {
            "passed": False,
            "errors": [f"Unable to validate: {exc}"],
            "episode_id": args.episode.name,
            "topics": {},
            "duration_s": 0.0,
        }
    args.episode.mkdir(parents=True, exist_ok=True)
    (args.episode / "validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("\n==== Recording Validation ====")
    print("Episode:", report["episode_id"])
    print("Duration:", report["duration_s"], "seconds")
    for name, value in report.get("topics", {}).items():
        print(f"{value['status']:14} {name} ({value['count']} messages)")
    for error in report["errors"]:
        print("[ERROR]", error)
    print("Overall:", "PASS" if report["passed"] else "FAIL")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
