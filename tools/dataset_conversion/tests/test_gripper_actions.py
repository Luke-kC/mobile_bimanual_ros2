from pathlib import Path
from types import SimpleNamespace as N

from tools.dataset_conversion.alignment import Sample, NS
from tools.dataset_conversion.convert import extract, build
from tools.dataset_conversion.schema import load_schema

SCHEMA = Path(__file__).resolve().parents[3] / 'config/dataset/schema.yaml'


def stamp(sec=0, nanosec=0):
    return N(sec=sec, nanosec=nanosec)


def trajectory(positions=(0.02,), joint='openarm_left_finger_joint1'):
    return N(joint_names=[joint], header=N(stamp=stamp()),
             points=[N(positions=[v], time_from_start=stamp(0, (i + 1) * 100_000_000))
                     for i, v in enumerate(positions)])


def controller(names=('openarm_right_finger_joint1', 'openarm_left_finger_joint1')):
    return N(joint_names=list(names), feedback=N(positions=[0.04, 0.02]),
             reference=N(positions=[0.05, 0.03]), error=N(positions=[0.01, 0.01]))


def test_gripper_trajectory_all_points_preserved():
    result = extract(trajectory((0.02, 0.05)), 'joint_trajectory_event', joint='openarm_left_finger_joint1')
    assert [p['position'] for p in result['points']] == [0.02, 0.05]
    assert [p['time_from_start_ns'] for p in result['points']] == [100_000_000, 200_000_000]


def test_gripper_trajectory_rejects_bad_joint_and_empty():
    assert extract(trajectory(joint='wrong'), 'joint_trajectory_event', joint='openarm_left_finger_joint1') is None
    msg = trajectory()
    msg.points = []
    assert extract(msg, 'joint_trajectory_event', joint='openarm_left_finger_joint1') is None


def test_gripper_trajectory_rejects_malformed_point():
    msg = trajectory()
    msg.points[0].positions = [0.01, 0.02]
    assert extract(msg, 'joint_trajectory_event', joint='openarm_left_finger_joint1') is None


def test_controller_feedback_extracts_by_joint_name():
    msg = controller()
    assert extract(msg, 'controller_feedback', joint='openarm_left_finger_joint1') == 0.02
    assert extract(msg, 'controller_reference', joint='openarm_right_finger_joint1') == 0.05
    assert extract(msg, 'controller_error', joint='openarm_left_finger_joint1') == 0.01


def test_events_survive_no_motion_mode():
    config = load_schema(SCHEMA)
    # mark observations optional so this test isolates the action pathway
    for spec in config['observations'].values():
        spec['required'] = False
    streams = {
        'mode': [Sample(0, 'no_motion')],
        'gripper_left.requested': [Sample(15_000_000, {'joint':'openarm_left_finger_joint1','points': [{'position':0.05,'time_from_start_ns':100_000_000}]})],
    }
    rows, _, _ = build(config, streams, 0, 100_000_000, profile='diagnostic')
    event = rows[0]['commands']['gripper_left.requested']
    assert event['valid'] and len(event['events']) == 1
    assert rows[1]['commands']['gripper_left.requested']['reason'] == 'no_event'


def test_schema_has_gripper_adapter():
    config = load_schema(SCHEMA)
    assert config['actions']['gripper_left']['field'] == 'joint_trajectory_event'
    assert config['actions']['gripper_right']['independent_of_mode'] is True
