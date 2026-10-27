"""Strict schema parsing independent of ROS and machine learning frameworks."""
from __future__ import annotations

import math
from pathlib import Path
import yaml

MODES = {"no_motion", "base_motion", "height_adjust", "manipulation"}
FIELDS = {"named_positions", "named_position", "data", "twist_planar", "pose_planar", "planar_twist", "data7", "joint_trajectory_event", "controller_feedback", "controller_reference", "controller_error"}
POLICIES = {"linear", "previous", "planar_pose"}
SEMANTICS = {"persistent_setpoint", "event_target", "expiring_velocity"}


def load_schema(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Expected schema_version: 1")
    dataset = raw.get("dataset", {})
    fps = dataset.get("fps")
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or not math.isfinite(fps) or fps <= 0:
        raise ValueError("dataset.fps must be positive and finite")
    if dataset.get("episode_policy") != "one_recording_per_episode":
        raise ValueError("Unsupported episode policy")
    if dataset.get("timestamp_policy") != "mcap_log_time":
        raise ValueError("Only mcap_log_time is currently supported")
    if dataset.get("normalize_grippers") is not False:
        raise ValueError("Gripper normalization is not implemented; retain raw signals")
    observations = raw.get("observations")
    actions = raw.get("actions")
    if not isinstance(observations, dict) or not observations or not isinstance(actions, dict):
        raise ValueError("observations and actions mappings required")
    for key, spec in observations.items():
        if not isinstance(spec, dict) or spec.get("alignment") not in POLICIES or spec.get("field") not in FIELDS:
            raise ValueError(f"Invalid observation: {key}")
        if not str(spec.get("topic", "")).startswith("/") or not spec.get("ros_type"):
            raise ValueError(f"Observation {key} needs topic and ros_type")
        bound = "max_gap_s" if spec["alignment"] in {"linear", "planar_pose"} else "max_age_s"
        if not isinstance(spec.get(bound), (int, float)) or not math.isfinite(spec[bound]) or spec[bound] <= 0:
            raise ValueError(f"Observation {key} needs positive {bound}")
        if spec["field"] == "named_positions" and (not spec.get("joints") or len(set(spec["joints"])) != len(spec["joints"])):
            raise ValueError(f"Invalid joint list: {key}")
        if spec["field"] == "named_position":
            if not isinstance(spec.get("joint"), str) or not spec["joint"].strip():
                raise ValueError(f"Observation {key} requires one nonempty joint name")
            if spec.get("ros_type") != "sensor_msgs/msg/JointState":
                raise ValueError(f"Observation {key} named_position requires JointState")
        if spec["field"] in {"controller_feedback", "controller_reference", "controller_error"}:
            if spec.get("ros_type") != "control_msgs/msg/JointTrajectoryControllerState" or not spec.get("joint"):
                raise ValueError(f"Invalid gripper controller observation {key}")
        if "units" not in spec:
            raise ValueError(f"Missing units: {key}")
    for key, spec in actions.items():
        if not isinstance(spec, dict) or spec.get("mode") not in MODES or spec.get("semantics") not in SEMANTICS:
            raise ValueError(f"Invalid action: {key}")
        if spec.get("field") not in FIELDS or not spec.get("ros_type") or "units" not in spec:
            raise ValueError(f"Invalid action fields: {key}")
        if "requested" not in spec and "authorized" not in spec:
            raise ValueError(f"Action {key} has no source")
        for role in ("requested", "authorized"):
            if role in spec and not str(spec[role]).startswith("/"):
                raise ValueError(f"Invalid topic for {key}.{role}")
        if spec["field"] == "joint_trajectory_event":
            if spec["ros_type"] != "trajectory_msgs/msg/JointTrajectory" or not spec.get("joint") or spec["semantics"] != "event_target":
                raise ValueError(f"Invalid gripper trajectory schema {key}")
        if spec["semantics"] == "expiring_velocity" and (not isinstance(spec.get("max_age_s"), (int, float)) or spec["max_age_s"] <= 0):
            raise ValueError(f"Missing timeout for {key}")
    return raw
