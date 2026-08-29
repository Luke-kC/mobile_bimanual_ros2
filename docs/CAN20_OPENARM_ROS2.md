# Classic CAN 2.0 note

This project intentionally uses classic CAN 2.0 at 1 Mbps for the OpenArm buses. For some reason, flexible data-rate keeps having issues, I may attempt to fix this at a future date.

As of the OpenArm sources checked in August 2026, the ros2_control Xacro macro supports a `can_fd` parameter but defaults it to `true`, while the stock bringup launch interface does not reliably expose a `can_fd` launch argument. This repo therefore contains `scripts/patch_openarm_can20.sh` as a temporary source-tree workaround.

After importing upstream dependencies:

```bash
./scripts/patch_openarm_can20.sh
./scripts/build.sh
```

Re-check this workaround whenever updating OpenArm dependencies. Remove the patch once upstream bringup exposes `can_fd:=false` directly.
