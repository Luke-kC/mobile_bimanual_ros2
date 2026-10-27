from tools.dataset_conversion.alignment import Sample, align, action_at, events_in_interval, grid, NS

def test_grid():
    t = grid(0, NS, 30)
    assert len(t) == 31 and t[1] == 33333333 and t[-1] == NS

def test_interpolation_and_gap():
    samples = [Sample(0, 0.0), Sample(NS // 10, 1.0)]
    assert align(samples, NS // 20, "linear", max_gap_s=.11)["value"] == .5
    assert align(samples, NS // 20, "linear", max_gap_s=.05)["reason"] == "gap_exceeded"
    assert not align(samples, -1, "linear", max_gap_s=.11)["valid"]

def test_modes_and_events():
    s = [Sample(0, [1.0]), Sample(NS, [2.0])]
    assert action_at(s, NS + 5, semantics="persistent_setpoint", mode_start_ns=NS)["value"] == [2.0]
    assert action_at(s, NS // 2, semantics="persistent_setpoint", mode_start_ns=NS // 4)["valid"] is False
    assert len(events_in_interval(s, 0, NS)) == 1

def test_expiring_velocity():
    s = [Sample(0, [.1, 0.0])]
    assert action_at(s, 40_000_000, semantics="expiring_velocity", mode_start_ns=0, max_age_s=.06)["valid"]
    assert not action_at(s, 70_000_000, semantics="expiring_velocity", mode_start_ns=0, max_age_s=.06)["valid"]

def test_angle_wrap():
    import math
    a = [Sample(0, [0, 0, math.radians(179)]), Sample(NS, [2, 0, math.radians(-179)])]
    middle = align(a, NS//2, "planar_pose", max_gap_s=1.1)["value"]
    assert middle[0] == 1.0 and abs(abs(middle[2]) - math.pi) < 1e-6
