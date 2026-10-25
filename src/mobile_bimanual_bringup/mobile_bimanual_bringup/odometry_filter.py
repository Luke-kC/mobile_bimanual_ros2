"""Velocity validation and planar odometry, independent of ROS."""

import math
from dataclasses import dataclass


@dataclass
class FilterConfig:
    max_linear_speed: float = 0.5
    max_angular_speed: float = 1.5
    max_linear_acceleration: float = 2.0
    max_angular_acceleration: float = 6.0
    max_hold_time: float = 0.1
    feedback_timeout: float = 0.2
    linear_stop_threshold: float = 0.01
    angular_stop_threshold: float = 0.03

    def __post_init__(self):
        for name, value in vars(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.feedback_timeout <= 0:
            raise ValueError("feedback_timeout must be positive")


class OdometryFilter:
    def __init__(self, config):
        self.config = config
        self.x = self.y = self.yaw = 0.0
        self.linear = self.angular = 0.0
        self.last_stamp = None
        self.accepted_stamp = None
        self.accepted_linear = self.accepted_angular = 0.0
        self.rejected_count = 0

    def expire(self):
        """Do not carry a velocity estimate across a feedback outage."""
        self.linear = self.angular = 0.0
        self.accepted_stamp = None
        self.last_stamp = None

    def update(self, stamp, linear, angular):
        """Return (accepted, reason); pose never uses incoming raw pose."""
        c = self.config
        if not math.isfinite(stamp):
            self.rejected_count += 1
            return False, "invalid timestamp"
        dt = 0.0 if self.last_stamp is None else stamp - self.last_stamp
        if dt <= 0 and self.last_stamp is not None:
            self.rejected_count += 1
            # Rebase on a backwards clock jump, without moving the pose.
            if dt < 0:
                self.expire()
                self.last_stamp = stamp
            return False, "non-increasing timestamp"
        if dt > c.feedback_timeout:
            self.expire()
            dt = 0.0

        reason = "accepted"
        if not math.isfinite(linear) or not math.isfinite(angular):
            reason = "non-finite velocity"
        elif abs(linear) > c.max_linear_speed or abs(angular) > c.max_angular_speed:
            reason = "speed limit"
        elif self.accepted_stamp is not None:
            elapsed = stamp - self.accepted_stamp
            stopped = (
                abs(linear) <= c.linear_stop_threshold
                and abs(angular) <= c.angular_stop_threshold
            )
            if not stopped and (
                (
                    c.max_linear_acceleration > 0
                    and abs(linear - self.accepted_linear) > c.max_linear_acceleration * elapsed
                )
                or (
                    c.max_angular_acceleration > 0
                    and abs(angular - self.accepted_angular) > c.max_angular_acceleration * elapsed
                )
            ):
                reason = "acceleration limit"

        accepted = reason == "accepted"
        if accepted:
            self.linear, self.angular = linear, angular
            self.accepted_linear, self.accepted_angular = linear, angular
            self.accepted_stamp = stamp
        else:
            self.rejected_count += 1
            # Integrate only the part of this interval within the hold budget.
            hold_remaining = 0.0 if self.accepted_stamp is None else max(
                0.0, self.accepted_stamp + c.max_hold_time - (stamp - dt)
            )
            dt = min(dt, hold_remaining)

        # Exact constant-twist integration, including simultaneous translation/turn.
        angle = self.angular * dt
        if abs(self.angular) > 1e-9:
            radius = self.linear / self.angular
            self.x += radius * (math.sin(self.yaw + angle) - math.sin(self.yaw))
            self.y += radius * (math.cos(self.yaw) - math.cos(self.yaw + angle))
        else:
            self.x += self.linear * dt * math.cos(self.yaw)
            self.y += self.linear * dt * math.sin(self.yaw)
        self.yaw = math.atan2(math.sin(self.yaw + angle), math.cos(self.yaw + angle))
        if not accepted and (
            self.accepted_stamp is None or stamp - self.accepted_stamp >= c.max_hold_time
        ):
            self.linear = self.angular = 0.0
        self.last_stamp = stamp
        return accepted, reason
