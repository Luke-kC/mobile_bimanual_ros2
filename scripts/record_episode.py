#!/usr/bin/env python3
"""One-episode interactive ROS 2 MCAP recorder. Never publishes to the robot."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config/recording/topics.yaml"


def load_contract(path: Path) -> dict:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("topic manifest must have schema_version: 1")
    topics = value.get("topics")
    if not isinstance(topics, dict) or not topics:
        raise ValueError("topic manifest requires a nonempty topics mapping")
    for name, spec in topics.items():
        if not isinstance(name, str) or not name.startswith("/"):
            raise ValueError(f"invalid topic name: {name}")
        if not isinstance(spec, dict) or not isinstance(spec.get("type"), str):
            raise ValueError(f"missing type for {name}")
    return value


def graph() -> dict[str, str]:
    result = subprocess.run(
        ["ros2", "topic", "list", "-t"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    discovered = {}
    for line in result.stdout.splitlines():
        match = re.fullmatch(r"\s*(/\S+)\s+\[([^\]]+)\]\s*", line)
        if match:
            discovered[match.group(1)] = match.group(2)
    return discovered


def select_topics(
    specs: dict, available: dict
) -> tuple[list[str], list[str], list[str]]:
    chosen, errors, absent_optional = [], [], []
    for name, definition in specs.items():
        actual = available.get(name)
        if actual is None:
            (
                errors if definition.get("required", False) else absent_optional
            ).append(f"{name}: not advertised")
        elif actual != definition["type"]:
            (
                errors if definition.get("required", False) else absent_optional
            ).append(f"{name}: expected {definition['type']}, got {actual}")
        else:
            chosen.append(name)
    return chosen, errors, absent_optional


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:64] or "task"


def write_yaml_atomic(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(yaml.safe_dump(value, sort_keys=False))
    temp.replace(path)


def read_choice(prompt: str, options: tuple[str, ...]) -> str:
    while True:
        try:
            response = input(prompt).strip().lower()
        except EOFError:
            raise RuntimeError("Interactive terminal input required") from None
        if response in options:
            return response
        print("Choose one of: " + ", ".join(options))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=ROOT / "data/recordings")
    parser.add_argument("--calibration-id", default="unassigned")
    args = parser.parse_args()
    if not shutil.which("ros2"):
        parser.error("ROS 2 CLI is not on PATH; source ROS 2 Jazzy first")
    contract = load_contract(args.manifest)
    task = input("Task description: ").strip()
    if not task:
        print("Task must be nonempty", file=sys.stderr)
        return 2
    chosen, errors, absent = select_topics(contract["topics"], graph())
    print("\nTopic preflight:")
    for name in chosen:
        print("  [READY]", name)
    for item in absent:
        print("  [OPTIONAL]", item)
    for item in errors:
        print("  [FAIL]", item)
    if errors:
        print(
            "Required topics missing or wrong type. Nothing recorded.",
            file=sys.stderr,
        )
        return 2
    if not chosen:
        print("No topics to record", file=sys.stderr)
        return 2
    episode_id = (
        datetime.now(timezone.utc).strftime("episode_%Y%m%dT%H%M%SZ_")
        + uuid.uuid4().hex[:8]
    )
    directory = args.output.expanduser().resolve() / slug(task) / episode_id
    # Exclusive create prevents overwriting a previous episode.
    directory.mkdir(parents=True, exist_ok=False)
    bag_path = directory / "recording"
    git = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    metadata = {
        "schema_version": 1,
        "episode_id": episode_id,
        "task": task,
        "result": "unreviewed",
        "recording_valid": False,
        "calibration_id": args.calibration_id,
        "git_commit": git.stdout.strip() if git.returncode == 0 else "unknown",
        "manifest": "topics.yaml",
        "bag": "recording",
        "topics_requested": chosen,
        "optional_missing_at_start": absent,
        "recording_status": "not_started",
    }
    shutil.copyfile(args.manifest, directory / "topics.yaml")
    write_yaml_atomic(directory / "metadata.yaml", metadata)
    print(f"\nEpisode: {episode_id}\nOutput: {directory}")
    input("Press ENTER to start recording...")
    cmd = ["ros2", "bag", "record", "-s", "mcap", "-o", str(bag_path), *chosen]
    started = datetime.now(timezone.utc)
    metadata.update(
        started_at=started.isoformat(), recording_status="recording"
    )
    write_yaml_atomic(directory / "metadata.yaml", metadata)
    process = subprocess.Popen(cmd, start_new_session=True)
    try:
        input("Recording. Press ENTER to stop...\n")
    except (EOFError, KeyboardInterrupt):
        print("\nRecording interrupted. Marking aborted.")
        forced_abort = True
    else:
        forced_abort = False
    # SIGINT gives rosbag2 a chance to finalize MCAP and write metadata.yaml.
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
    try:
        return_code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        print("Recorder did not stop gracefully; terminating process group.")
        os.killpg(process.pid, signal.SIGTERM)
        try:
            return_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return_code = process.wait()
    metadata.update(
        stopped_at=datetime.now(timezone.utc).isoformat(),
        recorder_exit_code=return_code,
        recording_status="finished",
    )
    result = (
        "aborted"
        if forced_abort
        else {"1": "success", "2": "failure", "3": "aborted"}[
            read_choice(
                "Result [1=success, 2=failure, 3=aborted]: ", ("1", "2", "3")
            )
        ]
    )
    metadata["result"] = result
    metadata["operator_notes"] = input("Optional notes: ").strip()
    write_yaml_atomic(directory / "metadata.yaml", metadata)
    validation = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_mcap.py"),
            str(directory),
        ],
        check=False,
    )
    # rosbag2 typically returns 0 on gracefully handled SIGINT; validate bag, not signal code.
    report_path = directory / "validation.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        metadata["recording_valid"] = bool(report.get("passed", False))
        write_yaml_atomic(directory / "metadata.yaml", metadata)
    if result != "success":
        answer = read_choice(
            "Keep failed/aborted episode? [Y/n]: ", ("", "y", "n")
        )
        if answer == "n":
            confirm = read_choice(
                "Permanently delete this episode? Type DELETE: ", ("delete", "")
            )
            if confirm == "delete":
                shutil.rmtree(directory)
                print("Episode deleted by operator.")
                return 0
    print(f"\nSaved: {directory}")
    return validation.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
        RuntimeError,
    ) as exc:
        print(f"Recorder error: {exc}", file=sys.stderr)
        sys.exit(2)
