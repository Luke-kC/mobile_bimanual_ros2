# Code Guidelines

This document defines the preferred code structure and conventions for `mobile_bimanual_ros2`.

These guidelines apply to both Python and C++ unless a section explicitly says otherwise.

---

## 1. Core principle: separate behavior from ROS

Code should be split conceptually into two layers:

```text
ROS / middleware / hardware adapters
                |
                v
        application core
```

The **core** contains the actual logic:

- validation
- safety checks
- state machines
- interpolation
- planning
- estimation
- kinematics
- control laws
- observation/action representations
- task logic
- mathematical utilities

The **adapter** contains integration details:

- ROS publishers/subscribers
- ROS messages
- ROS parameters
- ROS timers
- ROS services/actions
- logging
- TF publication/lookups
- ros2_control interfaces
- vendor SDK calls
- CAN/serial/network I/O

The dependency direction should be:

```text
ROS adapter      ---> core
hardware adapter ---> core
```

not:

```text
core ---> ROS
```

A core module should normally be usable from a unit test or standalone program without starting ROS.

This also means that we can write unit-tests for core independent of ROS, making development smoother.

Core should not import anything ROS related. ROS, however, can import from core.

### Example

Good:

```text
JointTrajectory ROS message
        |
        v
ROS conversion code
        |
        v
JointTarget domain object
        |
        v
BimanualController
        |
        v
ArmCommand domain object
        |
        v
ROS conversion code
        |
        v
controller command topic
```

Do not pass ROS messages deep into application logic. 

---

## 2. Treat ROS as an adapter, not the application architecture

ROS is the communication layer around the system. It should not define the internal representation of every concept.

Prefer project-owned data structures such as:

```python
@dataclass(frozen=True)
class JointTarget:
    positions: dict[str, float]
```

over making core logic accept ROS messages directly.

Similarly in C++, prefer project-owned structs/classes in the core rather than using ROS message types throughout the implementation.

This keeps the core independent of ROS and easier to test/reuse

---

## 3. ros2_control boundary

For actuator control, `ros2_control` should generally be treated as the boundary between high-level robot software and hardware-specific control.

Typical flow:

```text
task / VLA / teleop
        |
        v
project-owned command/safety logic
        |
        v
ROS adapter
        |
        v
ros2_control controller
        |
        v
hardware interface
        |
        v
vendor driver / CAN / actuator
```

High-level application code should not normally know:

- motor CAN IDs
- MIT packet formats
- raw encoder scaling

Those belong in hardware drivers or `ros2_control` hardware interfaces.

If a future feature requires our own control, such as:

- torque control
- inverse dynamics
- model-based control

implement it in a real-time-capable controller layer rather than in a Python ROS callback (so probably in C++).

---

## 4. Package structure

Prefer grouping files by responsibility rather than by implementation detail.

Example Python package:

```text
mobile_bimanual_control/
├── config/
│   └── control.yaml
│
├── mobile_bimanual_control/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── joints.py
│   │   ├── safety.py
│   │   ├── controller.py
│   │   └── interpolation.py
│   │
│   └── ros/
│       ├── __init__.py
│       ├── conversions.py
│       ├── command_bridge_node.py
│       └── joint_state_watch_node.py
│
└── test/
```

Example C++ package:

```text
mobile_bimanual_control/
├── include/mobile_bimanual_control/
│   ├── core/
│   │   ├── controller.hpp
│   │   ├── models.hpp
│   │   └── safety.hpp
│   │
│   └── ros/
│       └── command_bridge_node.hpp
│
├── src/
│   ├── core/
│   │   ├── controller.cpp
│   │   └── safety.cpp
│   │
│   └── ros/
│       └── command_bridge_node.cpp
│
└── test/
```

---

## 5. Domain models (Types)

Use project-owned data types to represent concepts such as:

- robot state
- joint state
- target commands
- controller output
- safety limits
- planner output
- observations
- VLA actions
- faults/status

Prefer explicit types over unstructured dictionaries or tuples when the data has meaningful semantics.

Python:

```python
@dataclass(frozen=True)
class ControllerConfig:
    command_rate_hz: float
    max_velocity_rad_s: float
    max_target_step_rad: float
```

C++:

```cpp
struct ControllerConfig
{
    double command_rate_hz;
    double max_velocity_rad_s;
    double max_target_step_rad;
};
```

Use immutable/read-only data where practical.

---

## 6. Type annotations and static typing

All non-trivial Python code should use type annotations.

Prefer:

```python
def update_state(
    self,
    state: JointStateSnapshot,
) -> bool:
    ...
```

over:

```python
def update_state(self, state):
    ...
```

Annotate:

- function parameters
- return values
- class members where the type is not obvious
- containers
- optional values

Examples:

```python
self._positions: dict[str, float] = {}
self._last_state: JointStateSnapshot | None = None
```

Avoid `Any` unless there is a specific reason.

For C++, prefer explicit types and strong domain types where useful. Avoid using plain integers or strings for concepts that would benefit from stronger semantics.

Static analysis is part of the development.

---

## 7. Public interfaces should be small

A class should expose only the operations other parts of the system actually need. This makes using it at the ROS level significantly easier.

Prefer:

```python
controller.update_state(state)
controller.set_target(target)
controller.step(now_sec)
```

over exposing internal dictionaries and requiring callers to manipulate state
directly.

Internal members should remain private unless there is a clear reason otherwise.

Python convention:

```python
self._state
self._target_positions
```

C++ convention:

```cpp
private:
    RobotState state_;
```

---

## 8. ROS node responsibilities

A ROS node should primarily:

1. declare/read parameters
2. subscribe to ROS messages
3. convert ROS messages to domain types
4. call core logic
5. convert results back to ROS messages
6. publish results
7. log important events

A ROS callback should not become the main location for substantial algorithms. Those live in core.

Good:

```python
def _target_callback(self, msg: JointTrajectory) -> None:
    target = target_from_ros(msg)
    result = self._controller.set_target(target, self._now_sec())
    self._handle_result(result)
```

---

## 9. Safety logic belongs below untrusted command sources

Treat teleop, scripted commands, planners, and VLA outputs as requests.

They should not directly command hardware.

Preferred flow:

```text
teleop / VLA / planner
        |
        v
requested action
        |
        v
validation + safety boundary
        |
        v
safe actuator command
```

Safety checks should remain independent of the command source.

Examples:

- finite-value checks
- joint limits
- velocity limits
- maximum target step
- stale-state detection
- tracking-error detection
- command timeout/watchdog

---

## 10. Units and frames must be explicit

We'll use SI units for this project (only exception being interacting with vendor code in different units)

Put units in the variable names:

```text
angle_rad
velocity_rad_s
timeout_sec
torque_nm
```

For transforms, document the convention and use consistent frame naming.

Do not silently change sign conventions or axis conventions at arbitrary layers.

---

## 11. Time handling

Be explicit about which clock a value belongs to.

Avoid mixing:

- wall clock
- ROS time
- simulation time
- device timestamps

ROS adapters are responsible for converting ROS time to the core representation.

---

## 12. Error handling

Validate inputs at boundaries.

Reject invalid input before mutating internal state.

For example, a target containing several joints should be validated completely before any of the requested joints are committed.

Preferred behavior:

```text
all values valid -> accept entire command
one value invalid -> reject entire command
```


Do not silently clamp invalid high-level commands. Rejection is easier to debug.

---

## 13. Logging

Logs should describe state changes and actionable events.

Good:

```text
Joint state became stale; suspending command updates
Joint state recovered; resuming command updates
Rejected target: joint7 outside limit
Tracking fault on joint4: 0.31 rad
```

Avoid logging high-rate normal operation every control cycle.

Use appropriate severity:

- DEBUG: detailed development information
- INFO: startup, mode changes, successful initialization
- WARN: rejected input, unusual but recoverable conditions
- ERROR: active faults, stale critical data, unsafe conditions

Core code should generally return structured results rather than directly
logging. Logging belongs in adapters.

---

## 14. Formatting and naming

### Python

Use:

- Ruff formatting
- 80-character line limit for this repository
- 4-space indentation
- `snake_case` for functions/variables/modules
- `PascalCase` for classes
- `UPPER_CASE` for constants
- double quotes consistently

### C++

I'll add a guideline for this when we need to.
