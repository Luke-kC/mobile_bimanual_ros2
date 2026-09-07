#!/bin/bash

# Name of the tmux session
SESSION="ros_workspace"

ROS_SETUP='source /opt/ros/${ROS_DISTRO:-jazzy}/setup.zsh && [[ -f /workspace/install/setup.zsh ]] && source /workspace/install/setup.zsh; clear'

# Start a new session, but don't attach to it yet
tmux new-session -d -s $SESSION

# Split into 4 quadrants
tmux split-window -h
tmux split-window -v
tmux select-pane -t 1
tmux split-window -v

# Send the ROS source command to all 4 panes
tmux send-keys -t 1 "$ROS_SETUP" C-m
tmux send-keys -t 2 "$ROS_SETUP" C-m
tmux send-keys -t 3 "$ROS_SETUP" C-m
tmux send-keys -t 4 "$ROS_SETUP" C-m

# Attach to the newly created session
tmux attach-session -t $SESSION
