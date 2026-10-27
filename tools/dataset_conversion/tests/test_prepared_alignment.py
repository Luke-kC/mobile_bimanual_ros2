"""Prepared-index regression against the public unprepared call path."""
import math
import random

import pytest

from tools.dataset_conversion.alignment import (
    NS, PreparedStream, Sample, action_at, align, events_in_interval,
)
from tools.dataset_conversion.convert import build


def test_prepared_and_unprepared_match_across_boundaries_and_gaps():
    rng = random.Random(7)
    timestamps = sorted(rng.sample(range(1, 8 * NS), 130))
    scalars = [Sample(t, math.sin(t / NS)) for t in timestamps]
    vectors = [Sample(s.timestamp_ns, [s.value, -s.value]) for s in scalars]
    poses = [Sample(s.timestamp_ns, [s.value, -s.value, 3.0 + s.value]) for s in scalars]
    categorical = [Sample(t, str(i % 3)) for i, t in enumerate(timestamps)]
    for samples, policies in [
        (scalars, ('linear',)), (vectors, ('linear',)),
        (poses, ('planar_pose',)), (categorical, ('previous',)),
    ]:
        prepared = PreparedStream.from_samples(samples)
        targets = [-1, 0, 1, timestamps[0], timestamps[-1], timestamps[-1] + 1]
        targets += rng.sample(range(0, 8 * NS), 230)
        for policy in policies:
            for target in targets:
                kwargs = {'max_age_s': 0.13} if policy == 'previous' else {'max_gap_s': 0.09}
                assert align(samples, target, policy, **kwargs) == align(prepared, target, policy, **kwargs)


def test_prepared_events_and_action_matching():
    samples = [Sample(t, [float(t)]) for t in (10, 30, 60, 90, 100)]
    prepared = PreparedStream.from_samples(samples)
    for start in (-1, 0, 10, 15, 30, 60, 90, 101):
        for end in (0, 11, 30, 61, 91, 101, 150):
            assert events_in_interval(samples, start, end) == events_in_interval(prepared, start, end)
        for target in (0, 10, 11, 29, 30, 60, 99, 100, 200):
            for semantics in ('expiring_velocity', 'persistent_setpoint', 'event_target'):
                kwargs = dict(semantics=semantics, mode_start_ns=start, max_age_s=1e-7)
                assert action_at(samples, target, **kwargs) == action_at(prepared, target, **kwargs)


def test_prepared_rejects_disordered_or_duplicate_times():
    for timestamps in ((4, 4), (8, 2)):
        with pytest.raises(ValueError, match='strictly increasing'):
            PreparedStream.from_samples([Sample(t, t) for t in timestamps])


def test_build_prepares_once_per_stream(monkeypatch):
    originals = PreparedStream.from_samples.__func__
    calls = []

    def counted(cls, values):
        calls.append(len(values))
        return originals(cls, values)

    monkeypatch.setattr(PreparedStream, 'from_samples', classmethod(counted))
    schema = {
        'dataset': {'fps': 30},
        'observations': {'a': {'alignment': 'linear', 'max_gap_s': 1.0, 'required': True}},
        'actions': {},
    }
    streams = {'a': [Sample(0, 1.0), Sample(NS, 2.0)]}
    rows, rejections, total = build(schema, streams, 0, NS, profile='diagnostic')
    assert total == len(rows) == 31
    assert rejections == {}
    assert calls == [2]  # not 31 times
