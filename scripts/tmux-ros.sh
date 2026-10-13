#!/bin/bash

# Name of the tmux session
SESSION="ros_workspace"

ROS_SETUP='source /opt/ros/${ROS_DISTRO:-jazzy}/setup.zsh && [[ -f /workspace/install/setup.zsh ]] && source /workspace/install/setup.zsh; clear'

if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux attach-session -t "$SESSION"
    exit 0
fi

# Start a new session, but don't attach to it yet
tmux new-session -d -s "$SESSION"

# Split into 4 quadrants
tmux split-window -t "$SESSION" -h
tmux split-window -t "$SESSION" -v
tmux select-pane -t "$SESSION:0.1"
tmux split-window -t "$SESSION" -v

# Send the ROS source command to all 4 panes
tmux send-keys -t "$SESSION:0.0" "$ROS_SETUP" C-m
tmux send-keys -t "$SESSION:0.1" "$ROS_SETUP" C-m
tmux send-keys -t "$SESSION:0.2" "$ROS_SETUP" C-m
tmux send-keys -t "$SESSION:0.3" "$ROS_SETUP" C-m

# Attach to the newly created session
tmux attach-session -t "$SESSION"
