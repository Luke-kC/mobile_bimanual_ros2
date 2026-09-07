# Data Visualization and Recording
This project uses Foxglove as the primary visualization software and `.mcap`
as the primary recorded data format.

## Live
To launch Foxglove by itself.
```zsh
ros2 launch mobile_bimanual_bringup observability.launch.py
```
Then open Foxglove and connect to:
```
ws://localhost:8765
```
## Record data to `.mcap`
```zsh
./scripts/record_mcap.sh
```
## Inspect the recorded file

```zsh
ros2 bag info bags/<session>
```

## Replay file as if it was live
```zsh
ros2 launch mobile_bimanual_bringup observability.launch.py
./scripts/play_mcap.sh bags/<session>
```
