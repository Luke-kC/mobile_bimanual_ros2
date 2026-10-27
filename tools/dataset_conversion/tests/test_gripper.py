from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.dataset_conversion.alignment import Sample
from tools.dataset_conversion.convert import build, extract
from tools.dataset_conversion.schema import load_schema

SCHEMA = Path(__file__).resolve().parents[3] / "config/dataset/schema.yaml"
LEFT = "openarm_left_finger_joint1"
RIGHT = "openarm_right_finger_joint1"


def joint_state(names, positions):
    return SimpleNamespace(name=names, position=positions)


def test_gripper_schema_contract():
    schema = load_schema(SCHEMA)
    assert schema["dataset"]["normalize_grippers"] is False
    for side, joint in (("left", LEFT), ("right", RIGHT)):
        spec = schema["observations"][f"{side}_gripper"]
        assert spec["joint"] == joint
        assert spec["field"] == "named_position"
        assert spec["required"] is True
        assert spec["units"] == "nominal_m"


def test_joint_name_not_index_and_no_clamping():
    msg = joint_state([RIGHT, "random_joint", LEFT], [0.054601, 3.0, 0.054569])
    assert extract(msg, "named_position", joint=LEFT) == 0.054569
    assert extract(msg, "named_position", joint=RIGHT) == 0.054601
    reordered = joint_state([LEFT, RIGHT], [0.054569, 0.054601])
    assert extract(reordered, "named_position", joint=LEFT) == 0.054569
    assert extract(reordered, "named_position", joint=RIGHT) == 0.054601


@pytest.mark.parametrize("msg", [
    joint_state([LEFT], [0.001]),  # requested right joint absent
    joint_state([RIGHT, RIGHT], [0.002, 0.003]),  # duplicate names
    joint_state([RIGHT, LEFT], [0.005]),  # malformed lengths
    joint_state([RIGHT], [float("nan")]),
    joint_state([RIGHT], [float("inf")]),
])
def test_invalid_gripper_reading_rejected(msg):
    assert extract(msg, "named_position", joint=RIGHT) is None


def test_interpolation_and_raw_output():
    schema = load_schema(SCHEMA)
    for spec in schema["observations"].values():
        spec["required"] = False
    streams = {
        "left_gripper": [Sample(0, 0.002428), Sample(20_000_000, 0.054569)],
        "right_gripper": [Sample(0, 0.005522), Sample(20_000_000, 0.054601)],
    }
    rows, _, _ = build(schema, streams, 10_000_000, 10_000_000, profile="diagnostic")
    obs = rows[0]["observations"]
    assert obs["left_gripper"]["valid"] is True
    assert obs["right_gripper"]["valid"] is True
    assert obs["left_gripper"]["value"] == pytest.approx((0.002428 + 0.054569) / 2)
    assert obs["right_gripper"]["value"] == pytest.approx((0.005522 + 0.054601) / 2)


def test_missing_gripper_rejected_in_training():
    schema = load_schema(SCHEMA)
    for key, spec in schema["observations"].items():
        spec["required"] = key == "right_gripper"
    rows, rejected, _ = build(schema, {}, 0, 0, profile="diagnostic")
    assert rows[0]["observations"]["right_gripper"]["reason"] == "no_samples"
    assert rejected["right_gripper"] == 1
