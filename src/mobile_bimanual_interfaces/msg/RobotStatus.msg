# RobotMode Constants
uint8 MODE_BOOTING=1
uint8 MODE_INITIALIZING=2
uint8 MODE_READY=3
uint8 MODE_DEGRADED=4
uint8 MODE_FAULT=5
uint8 MODE_ESTOP=6

# Status Fields
uint8 mode
bool external_commands_allowed

bool hardware_active
bool controllers_active
bool joint_state_complete
bool joint_state_fresh

string[] not_ready_components
string[] active_faults
