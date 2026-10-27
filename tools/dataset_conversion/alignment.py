"""Deterministic alignment for timestamped scalar/vector values."""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Any, Sequence

NS = 1_000_000_000

@dataclass(frozen=True)
class Sample:
    timestamp_ns: int
    value: Any
    header_stamp_ns: int | None = None
    publish_time_ns: int | None = None


def grid(start_ns: int, end_ns: int, fps: int) -> list[int]:
    """Inclusive regular grid; nanosecond integers avoid floating point drift."""
    if fps <= 0 or start_ns > end_ns:
        raise ValueError("Invalid time grid")
    return [start_ns + (k * NS) // fps for k in range(((end_ns - start_ns) * fps) // NS + 1)]


@dataclass(frozen=True)
class PreparedStream:
    """Timestamp index constructed once, shared across frame alignments."""
    samples: Sequence[Sample]
    timestamps_ns: tuple[int, ...]

    @classmethod
    def from_samples(cls, samples: Sequence[Sample]) -> "PreparedStream":
        ts = tuple(s.timestamp_ns for s in samples)
        if any(a >= b for a, b in zip(ts, ts[1:])):
            raise ValueError("Stream timestamps must be strictly increasing")
        return cls(samples, ts)


def _prepared(samples: Sequence[Sample] | PreparedStream) -> PreparedStream:
    return samples if isinstance(samples, PreparedStream) else PreparedStream.from_samples(samples)


def align(samples: Sequence[Sample] | PreparedStream, target_ns: int, policy: str, *,
          max_gap_s: float = 0.0, max_age_s: float = 0.0) -> dict:
    """Return validity and source provenance. Never extrapolate continuous states."""
    prepared = _prepared(samples)
    samples, ts = prepared.samples, prepared.timestamps_ns
    if not samples:
        return {"valid": False, "reason": "no_samples"}
    i = bisect.bisect_right(ts, target_ns)
    if policy == "previous":
        if i == 0:
            return {"valid": False, "reason": "no_previous_sample"}
        s = samples[i - 1]
        if target_ns - s.timestamp_ns > round(max_age_s * NS):
            return {"valid": False, "reason": "stale"}
        return {"valid": True, "value": s.value, "source_times_ns": [s.timestamp_ns]}
    if policy not in {"linear", "planar_pose"}:
        raise ValueError(f"Unknown interpolation: {policy}")
    if i > 0 and ts[i - 1] == target_ns:
        return {"valid": True, "value": samples[i - 1].value, "source_times_ns": [target_ns]}
    if i == 0 or i == len(samples):
        return {"valid": False, "reason": "outside_measurement_range"}
    left, right = samples[i - 1], samples[i]
    if right.timestamp_ns - left.timestamp_ns > round(max_gap_s * NS):
        return {"valid": False, "reason": "gap_exceeded"}
    alpha = (target_ns - left.timestamp_ns) / (right.timestamp_ns - left.timestamp_ns)
    a, b = left.value, right.value
    scalar = isinstance(a, (float, int)) and not isinstance(a, bool)
    if scalar:
        values = float(a) + alpha * (float(b) - float(a))
    else:
        if len(a) != len(b):
            return {"valid": False, "reason": "shape_mismatch"}
        values = [float(x) + alpha * (float(y) - float(x)) for x, y in zip(a, b)]
        if policy == "planar_pose":
            if len(values) != 3:
                raise ValueError("planar_pose needs x, y, yaw")
            diff = (float(b[2]) - float(a[2]) + math.pi) % (2 * math.pi) - math.pi
            values[2] = (float(a[2]) + alpha * diff + math.pi) % (2 * math.pi) - math.pi
    return {"valid": True, "value": values, "source_times_ns": [left.timestamp_ns, right.timestamp_ns]}


def events_in_interval(samples: Sequence[Sample] | PreparedStream, start_ns: int,
                       end_ns: int) -> list[Sample]:
    """Half-open interval: events cannot be replaced by held pseudo-actions."""
    prepared = _prepared(samples)
    begin = bisect.bisect_left(prepared.timestamps_ns, start_ns)
    end = bisect.bisect_left(prepared.timestamps_ns, end_ns)
    return list(prepared.samples[begin:end])


def action_at(samples: Sequence[Sample] | PreparedStream, target_ns: int, *,
              semantics: str, mode_start_ns: int, max_age_s: float = 0.0) -> dict:
    """Command validity resets on every mode entry; hold commands do not cross modes."""
    prepared = _prepared(samples)
    left = bisect.bisect_left(prepared.timestamps_ns, mode_start_ns)
    right = bisect.bisect_right(prepared.timestamps_ns, target_ns)
    if semantics == "event_target":
        return {"valid": False, "reason": "event_only"}
    if semantics == "expiring_velocity":
        if right <= left:
            return {"valid": False, "reason": "no_samples"}
        latest = prepared.samples[right - 1]
        if target_ns - latest.timestamp_ns > round(max_age_s * NS):
            return {"valid": False, "reason": "stale"}
        return {"valid": True, "value": latest.value,
                "source_times_ns": [latest.timestamp_ns]}
    if semantics == "persistent_setpoint":
        if right <= left:
            return {"valid": False, "reason": "no_command_in_mode"}
        latest = prepared.samples[right - 1]
        return {"valid": True, "value": latest.value,
                "source_times_ns": [latest.timestamp_ns]}
    raise ValueError(f"Unknown semantics {semantics}")
