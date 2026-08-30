Live:
    ros2 launch mobile_bimanual_bringup observability.launch.py
    Foxglove → ws://localhost:8765

Record:
    ./scripts/record_mcap.sh

Inspect:
    ros2 bag info bags/<session>

Replay:
    ros2 launch mobile_bimanual_bringup observability.launch.py
    ./scripts/play_mcap.sh bags/<session>
