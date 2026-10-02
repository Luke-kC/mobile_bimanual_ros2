#include <Arduino.h>

#include <cmath>
#include <cstdio>
#include <cstring>

namespace
{

// =============================================================================
// Hardware
// =============================================================================

constexpr gpio_num_t kUpPin = GPIO_NUM_17;
constexpr gpio_num_t kStopPin = GPIO_NUM_18;
constexpr gpio_num_t kDownPin = GPIO_NUM_23;
constexpr gpio_num_t kUnlockedSensePin = GPIO_NUM_19;
constexpr gpio_num_t kPositionPin = GPIO_NUM_34;

// =============================================================================
// Configuration
// =============================================================================

// Pedestal
constexpr float kPositionDeadbandM = 0.005F;

constexpr float kMinTargetPositionM = 0.010F;
constexpr float kMaxTargetPositionM = 0.408F;

// Button/controller timing
constexpr uint32_t kButtonPulseDurationMs = 200;
constexpr uint32_t kUnlockTimeoutMs = 7000;
constexpr uint32_t kUnlockSettleDurationMs = 500;
constexpr uint32_t kDirectionChangeDelayMs = 500;

// Communications / safety
constexpr uint32_t kHeartbeatTimeoutMs = 500;
constexpr uint32_t kPositionStaleTimeoutMs = 250;

// Telemetry
constexpr uint32_t kTelemetryPeriodMs = 50;

// String-pot position sensing
//
// CALT CWP-S1000V1:
//   - sensor output: 0-5 V
//   - divider: 10 kOhm from OUT+ to ADC, 6.8 kOhm from ADC to GND
//   - ADC pin: GPIO34
//
// Position is defined as extension from the fully-collapsed pedestal:
//   0.000 m -> top surface at 30.2 cm above ground
//   0.418 m -> top surface at 72.0 cm above ground
//
// Calibration from the installed sensor:
//   0.9483 V -> 0.000 m
//   3.0215 V -> 0.418 m
//
// The intermediate calibration measurements were very close to linear, so
// endpoint-constrained linear interpolation is used.
constexpr uint32_t kStringPotMeasurementPeriodMs = 20;  // 50 Hz result rate
constexpr uint32_t kStringPotSampleSpacingUs = 200;
constexpr size_t kStringPotSampleCount = 16;
constexpr float kStringPotFilterAlpha = 0.10F;

constexpr float kStringPotDividerScale = 2.4706F;  // (10k + 6.8k) / 6.8k
constexpr float kStringPotMinSensorV = 0.9483F;
constexpr float kStringPotMaxSensorV = 3.0215F;
constexpr float kPedestalStrokeM = 0.418F;

// Allow a small amount of voltage noise/drift beyond the calibrated endpoints.
// Values inside this margin are clamped to the nearest endpoint. Values farther
// outside the range are rejected and will eventually trigger POSITION_STALE
// while a goal is active.
//
// 0.05 V corresponds to roughly 10 mm of pedestal extension.
constexpr float kStringPotCalibrationMarginV = 0.05F;

bool string_pot_voltage_to_position_m(const float sensor_v, float& position_m)
{
    if (!std::isfinite(sensor_v))
    {
        return false;
    }

    if (sensor_v < kStringPotMinSensorV - kStringPotCalibrationMarginV ||
        sensor_v > kStringPotMaxSensorV + kStringPotCalibrationMarginV)
    {
        return false;
    }

    float clamped_sensor_v = sensor_v;

    if (clamped_sensor_v < kStringPotMinSensorV)
    {
        clamped_sensor_v = kStringPotMinSensorV;
    }
    else if (clamped_sensor_v > kStringPotMaxSensorV)
    {
        clamped_sensor_v = kStringPotMaxSensorV;
    }

    const float normalized = (clamped_sensor_v - kStringPotMinSensorV) /
                             (kStringPotMaxSensorV - kStringPotMinSensorV);

    position_m = normalized * kPedestalStrokeM;

    return std::isfinite(position_m);
}

// =============================================================================
// Position sensor abstraction
// =============================================================================

class PositionSensor
{
   public:
    virtual ~PositionSensor() = default;

    virtual bool begin() = 0;
    virtual void update() = 0;

    virtual bool has_valid_measurement() const = 0;
    virtual float position_m() const = 0;
    virtual uint32_t last_valid_update_ms() const = 0;
};

// -----------------------------------------------------------------------------
// CALT CWP-S1000V1 string-pot implementation
// -----------------------------------------------------------------------------
class StringPotPositionSensor final : public PositionSensor
{
   public:
    bool begin() override
    {
        pinMode(kPositionPin, INPUT);

        analogReadResolution(12);
        analogSetPinAttenuation(kPositionPin, ADC_6db);

        // Let the first batch start immediately.
        last_batch_start_ms_ = millis() - kStringPotMeasurementPeriodMs;
        last_sample_us_ = micros() - kStringPotSampleSpacingUs;

        return true;
    }

    void update() override
    {
        const uint32_t now_ms = millis();

        // Start a new 16-sample batch at 50 Hz.
        if (sample_count_ == 0)
        {
            if (now_ms - last_batch_start_ms_ < kStringPotMeasurementPeriodMs)
            {
                return;
            }

            last_batch_start_ms_ = now_ms;
            adc_mv_sum_ = 0;
        }

        // Spread the samples across loop() calls instead of blocking for the
        // whole averaging window.
        const uint32_t now_us = micros();

        if (now_us - last_sample_us_ < kStringPotSampleSpacingUs)
        {
            return;
        }

        last_sample_us_ = now_us;

        adc_mv_sum_ += analogReadMilliVolts(kPositionPin);
        ++sample_count_;

        if (sample_count_ < kStringPotSampleCount)
        {
            return;
        }

        const float adc_v =
            (adc_mv_sum_ / static_cast<float>(kStringPotSampleCount)) / 1000.0F;

        sample_count_ = 0;

        if (!filter_initialized_)
        {
            filtered_adc_v_ = adc_v;
            filter_initialized_ = true;
        }
        else
        {
            filtered_adc_v_ +=
                kStringPotFilterAlpha * (adc_v - filtered_adc_v_);
        }

        adc_voltage_v_ = adc_v;
        sensor_voltage_v_ = filtered_adc_v_ * kStringPotDividerScale;

        float position_m = 0.0F;

        if (!string_pot_voltage_to_position_m(sensor_voltage_v_, position_m))
        {
            return;
        }

        position_m_ = position_m;
        last_valid_update_ms_ = millis();
        has_valid_measurement_ = true;
    }

    bool has_valid_measurement() const override
    {
        return has_valid_measurement_;
    }

    float position_m() const override { return position_m_; }

    float adc_voltage_v() const { return adc_voltage_v_; }

    float sensor_voltage_v() const { return sensor_voltage_v_; }

    uint32_t last_valid_update_ms() const override
    {
        return last_valid_update_ms_;
    }

   private:
    float position_m_ = 0.0F;
    float adc_voltage_v_ = 0.0F;
    float sensor_voltage_v_ = 0.0F;
    float filtered_adc_v_ = 0.0F;

    uint32_t adc_mv_sum_ = 0;
    size_t sample_count_ = 0;

    uint32_t last_batch_start_ms_ = 0;
    uint32_t last_sample_us_ = 0;
    uint32_t last_valid_update_ms_ = 0;

    bool filter_initialized_ = false;
    bool has_valid_measurement_ = false;
};

StringPotPositionSensor position_sensor;

// =============================================================================
// Pedestal state
// =============================================================================

enum class TaskState
{
    kIdle,

    kUnlocking,
    kUnlockSettling,

    kMovingUp,
    kMovingDown,

    kStopping,
    kReverseWait,

    kFault,
};

enum class CommandedMotion
{
    kStopped,
    kUp,
    kDown,
};

// =============================================================================
// Button output state
// =============================================================================

enum class ButtonOutputState
{
    kIdle,
    kPulsing,
    kHolding,
};

ButtonOutputState button_output_state = ButtonOutputState::kIdle;

gpio_num_t active_button_pin = kStopPin;
uint32_t button_action_start_ms = 0;

// =============================================================================
// Persistent application state
// =============================================================================

float target_position_m = 0.0F;
float measured_position_m = 0.0F;

bool position_valid = false;
uint32_t last_position_update_ms = 0;

bool goal_active = false;
bool goal_completion_pending = false;
bool reverse_after_stop = false;

TaskState task_state = TaskState::kIdle;
uint32_t task_state_entry_ms = 0;

CommandedMotion commanded_motion = CommandedMotion::kStopped;

uint32_t last_heartbeat_ms = 0;
uint32_t last_telemetry_ms = 0;

const char* fault_reason = "NONE";

// =============================================================================
// Forward declarations
// =============================================================================

void process_serial();

void update_position_sensor();
void update_button_output();
void update_task_state_machine();

void check_watchdog();
void publish_telemetry();

void set_task_state(TaskState new_state);
void enter_fault(const char* reason);

void request_stop(bool reverse_after);
void choose_motion_from_error();

bool position_is_fresh();
bool is_unlocked();

// =============================================================================
// Small helpers
// =============================================================================

bool is_unlocked() { return digitalRead(kUnlockedSensePin) == LOW; }

bool position_is_fresh()
{
    if (!position_valid)
    {
        return false;
    }

    return millis() - last_position_update_ms <= kPositionStaleTimeoutMs;
}

const char* task_state_name()
{
    switch (task_state)
    {
        case TaskState::kIdle:
            return "IDLE";

        case TaskState::kUnlocking:
            return "UNLOCKING";

        case TaskState::kUnlockSettling:
            return "UNLOCK_SETTLING";

        case TaskState::kMovingUp:
            return "MOVING_UP";

        case TaskState::kMovingDown:
            return "MOVING_DOWN";

        case TaskState::kStopping:
            return "STOPPING";

        case TaskState::kReverseWait:
            return "REVERSE_WAIT";

        case TaskState::kFault:
            return "FAULT";
    }

    return "UNKNOWN";
}

// =============================================================================
// Nonblocking button output
// =============================================================================

void release_all_buttons()
{
    digitalWrite(kUpPin, LOW);
    digitalWrite(kStopPin, LOW);
    digitalWrite(kDownPin, LOW);

    button_output_state = ButtonOutputState::kIdle;
}

void start_button_pulse(const gpio_num_t pin)
{
    release_all_buttons();

    active_button_pin = pin;
    button_action_start_ms = millis();

    digitalWrite(active_button_pin, HIGH);

    button_output_state = ButtonOutputState::kPulsing;
}

void start_button_hold(const gpio_num_t pin)
{
    release_all_buttons();

    active_button_pin = pin;

    digitalWrite(active_button_pin, HIGH);

    button_output_state = ButtonOutputState::kHolding;
}

bool button_output_idle()
{
    return button_output_state == ButtonOutputState::kIdle;
}

void update_button_output()
{
    if (button_output_state != ButtonOutputState::kPulsing)
    {
        return;
    }

    if (millis() - button_action_start_ms < kButtonPulseDurationMs)
    {
        return;
    }

    digitalWrite(active_button_pin, LOW);

    button_output_state = ButtonOutputState::kIdle;
}

// =============================================================================
// Position sensor
// =============================================================================

void update_position_sensor()
{
    position_sensor.update();

    if (!position_sensor.has_valid_measurement())
    {
        position_valid = false;
        return;
    }

    measured_position_m = position_sensor.position_m();
    last_position_update_ms = position_sensor.last_valid_update_ms();

    position_valid = true;
}

// =============================================================================
// Task state entry handling
// =============================================================================

void set_task_state(const TaskState new_state)
{
    if (new_state == task_state)
    {
        return;
    }

    // No button from the previous state should remain asserted when
    // transitioning to a new state.
    release_all_buttons();

    task_state = new_state;
    task_state_entry_ms = millis();

    switch (task_state)
    {
        case TaskState::kIdle:
            commanded_motion = CommandedMotion::kStopped;
            break;

        case TaskState::kUnlocking:
            commanded_motion = CommandedMotion::kStopped;

            // Unlock gesture requires holding DOWN.
            start_button_hold(kDownPin);
            break;

        case TaskState::kUnlockSettling:
            commanded_motion = CommandedMotion::kStopped;
            break;

        case TaskState::kMovingUp:
            start_button_pulse(kUpPin);
            commanded_motion = CommandedMotion::kUp;
            break;

        case TaskState::kMovingDown:
            start_button_pulse(kDownPin);
            commanded_motion = CommandedMotion::kDown;
            break;

        case TaskState::kStopping:
            start_button_pulse(kStopPin);
            commanded_motion = CommandedMotion::kStopped;
            break;

        case TaskState::kReverseWait:
            commanded_motion = CommandedMotion::kStopped;
            break;

        case TaskState::kFault:
            start_button_pulse(kStopPin);
            commanded_motion = CommandedMotion::kStopped;
            break;
    }
}

// =============================================================================
// Fault handling
// =============================================================================

void enter_fault(const char* reason)
{
    fault_reason = reason;

    goal_active = false;
    goal_completion_pending = false;
    reverse_after_stop = false;

    set_task_state(TaskState::kFault);

    Serial.print("EVENT FAULT ");
    Serial.println(reason);
}

// =============================================================================
// Goal / movement helpers
// =============================================================================

void request_stop(const bool reverse_after)
{
    reverse_after_stop = reverse_after;

    set_task_state(TaskState::kStopping);
}

void choose_motion_from_error()
{
    if (!goal_active)
    {
        set_task_state(TaskState::kIdle);
        return;
    }

    if (!position_is_fresh())
    {
        enter_fault("POSITION_STALE");
        return;
    }

    const float error_m = target_position_m - measured_position_m;

    if (std::fabs(error_m) <= kPositionDeadbandM)
    {
        goal_active = false;

        Serial.println("EVENT GOAL_REACHED");

        set_task_state(TaskState::kIdle);
        return;
    }

    if (!is_unlocked())
    {
        set_task_state(TaskState::kUnlocking);
        return;
    }

    if (error_m > 0.0F)
    {
        set_task_state(TaskState::kMovingUp);
    }
    else
    {
        set_task_state(TaskState::kMovingDown);
    }
}

// =============================================================================
// Main task state machine
// =============================================================================

void update_task_state_machine()
{
    if (task_state == TaskState::kFault)
    {
        return;
    }

    // Once a position goal is active, loss of position feedback is unsafe.
    if (goal_active && !position_is_fresh())
    {
        enter_fault("POSITION_STALE");
        return;
    }

    const float error_m = target_position_m - measured_position_m;

    switch (task_state)
    {
        // -----------------------------------------------------------------
        case TaskState::kIdle:
        {
            if (!goal_active)
            {
                return;
            }

            choose_motion_from_error();
            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kUnlocking:
        {
            // A new target could arrive while we're unlocking and make
            // movement unnecessary.
            if (goal_active && std::fabs(error_m) <= kPositionDeadbandM)
            {
                release_all_buttons();

                goal_active = false;

                Serial.println("EVENT GOAL_REACHED");

                set_task_state(TaskState::kIdle);
                return;
            }

            if (is_unlocked())
            {
                // Releasing DOWN occurs as part of the state transition.
                set_task_state(TaskState::kUnlockSettling);
                return;
            }

            if (millis() - task_state_entry_ms > kUnlockTimeoutMs)
            {
                enter_fault("UNLOCK_TIMEOUT");
                return;
            }

            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kUnlockSettling:
        {
            if (millis() - task_state_entry_ms < kUnlockSettleDurationMs)
            {
                return;
            }

            if (!is_unlocked())
            {
                enter_fault("UNLOCK_FAILED");
                return;
            }

            choose_motion_from_error();
            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kMovingUp:
        {
            if (!goal_active)
            {
                request_stop(false);
                return;
            }

            if (std::fabs(error_m) <= kPositionDeadbandM)
            {
                goal_active = false;
                goal_completion_pending = true;

                request_stop(false);
                return;
            }

            // Target moved below us, or we overshot enough that we now
            // need to reverse direction.
            if (error_m < -kPositionDeadbandM)
            {
                request_stop(true);
                return;
            }

            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kMovingDown:
        {
            if (!goal_active)
            {
                request_stop(false);
                return;
            }

            if (std::fabs(error_m) <= kPositionDeadbandM)
            {
                goal_active = false;
                goal_completion_pending = true;

                request_stop(false);
                return;
            }

            if (error_m > kPositionDeadbandM)
            {
                request_stop(true);
                return;
            }

            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kStopping:
        {
            if (!button_output_idle())
            {
                return;
            }

            if (goal_completion_pending)
            {
                goal_completion_pending = false;

                Serial.println("EVENT GOAL_REACHED");

                set_task_state(TaskState::kIdle);
                return;
            }

            if (reverse_after_stop && goal_active)
            {
                reverse_after_stop = false;

                set_task_state(TaskState::kReverseWait);
                return;
            }

            set_task_state(TaskState::kIdle);
            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kReverseWait:
        {
            if (!goal_active)
            {
                set_task_state(TaskState::kIdle);
                return;
            }

            if (millis() - task_state_entry_ms < kDirectionChangeDelayMs)
            {
                return;
            }

            choose_motion_from_error();
            return;
        }

        // -----------------------------------------------------------------
        case TaskState::kFault:
            return;
    }
}

// =============================================================================
// Serial protocol
// =============================================================================
//
// Host -> ESP
//
//   P 0.250
//       Request position in meters.
//
//   H
//       Heartbeat.
//
//   S
//       Cancel current goal and stop.
//
//   Q
//       Query state.
//
//   R
//       Clear a recoverable fault.
//
// All commands are newline terminated.
//
// =============================================================================

void accept_position_goal(const float requested_position_m)
{
    if (!std::isfinite(requested_position_m))
    {
        Serial.println("ERR TARGET_INVALID");
        return;
    }

    if (requested_position_m < kMinTargetPositionM ||
        requested_position_m > kMaxTargetPositionM)
    {
        Serial.println("ERR TARGET_RANGE");
        return;
    }

    if (task_state == TaskState::kFault)
    {
        Serial.println("ERR FAULT_ACTIVE");
        return;
    }

    if (!position_is_fresh())
    {
        Serial.println("ERR POSITION_INVALID");
        return;
    }

    target_position_m = requested_position_m;

    goal_active = true;
    goal_completion_pending = false;

    // If we're currently stopping because of an old goal, let that stop
    // complete. IDLE will then process this new goal.
    reverse_after_stop = false;

    last_heartbeat_ms = millis();

    Serial.print("ACK TARGET ");
    Serial.println(target_position_m, 4);
}

void stop_current_goal()
{
    goal_active = false;
    goal_completion_pending = false;
    reverse_after_stop = false;

    if (task_state != TaskState::kFault)
    {
        set_task_state(TaskState::kStopping);
    }
    else
    {
        // Still make sure all held outputs are released and STOP is sent.
        release_all_buttons();
        start_button_pulse(kStopPin);
    }

    Serial.println("ACK STOP");
}

void report_state()
{
    Serial.print("STATE ");
    Serial.print(task_state_name());

    Serial.print(" POSITION_M ");

    if (position_is_fresh())
    {
        Serial.print(measured_position_m, 4);
    }
    else
    {
        Serial.print("INVALID");
    }

    Serial.print(" SENSOR_V ");

    if (position_is_fresh())
    {
        Serial.print(position_sensor.sensor_voltage_v(), 4);
    }
    else
    {
        Serial.print("INVALID");
    }

    Serial.print(" TARGET_M ");
    Serial.print(target_position_m, 4);

    Serial.print(" GOAL_ACTIVE ");
    Serial.print(goal_active ? 1 : 0);

    Serial.print(" UNLOCKED ");
    Serial.print(is_unlocked() ? 1 : 0);

    Serial.print(" FAULT ");
    Serial.println(fault_reason);
}

void clear_fault()
{
    if (task_state != TaskState::kFault)
    {
        Serial.println("ACK RESET");
        return;
    }

    if (!position_is_fresh())
    {
        Serial.println("ERR POSITION_INVALID");
        return;
    }

    fault_reason = "NONE";

    goal_active = false;
    goal_completion_pending = false;
    reverse_after_stop = false;

    set_task_state(TaskState::kIdle);

    Serial.println("ACK RESET");
}

void process_serial_line(const char* line)
{
    if (std::strcmp(line, "H") == 0)
    {
        last_heartbeat_ms = millis();
        return;
    }

    if (std::strcmp(line, "S") == 0)
    {
        stop_current_goal();
        return;
    }

    if (std::strcmp(line, "Q") == 0)
    {
        report_state();
        return;
    }

    if (std::strcmp(line, "R") == 0)
    {
        clear_fault();
        return;
    }

    float requested_position_m = 0.0F;

    if (std::sscanf(line, "P %f", &requested_position_m) == 1)
    {
        accept_position_goal(requested_position_m);
        return;
    }

    Serial.println("ERR UNKNOWN_COMMAND");
}

void process_serial()
{
    constexpr size_t kBufferSize = 64;

    static char buffer[kBufferSize];
    static size_t length = 0;

    while (Serial.available() > 0)
    {
        const char c = static_cast<char>(Serial.read());

        if (c == '\r')
        {
            continue;
        }

        if (c == '\n')
        {
            if (length == 0)
            {
                continue;
            }

            buffer[length] = '\0';

            process_serial_line(buffer);

            length = 0;
            continue;
        }

        if (length >= kBufferSize - 1)
        {
            length = 0;

            Serial.println("ERR COMMAND_TOO_LONG");
            continue;
        }

        buffer[length++] = c;
    }
}

// =============================================================================
// Watchdog
// =============================================================================

void check_watchdog()
{
    if (!goal_active)
    {
        return;
    }

    if (millis() - last_heartbeat_ms <= kHeartbeatTimeoutMs)
    {
        return;
    }

    enter_fault("HOST_TIMEOUT");
}

// =============================================================================
// Telemetry
// =============================================================================
void publish_telemetry()
{
    const uint32_t now_ms = millis();

    if (now_ms - last_telemetry_ms < kTelemetryPeriodMs)
    {
        return;
    }

    last_telemetry_ms = now_ms;

    Serial.print("TEL POSITION_M ");

    if (position_is_fresh())
    {
        Serial.print(measured_position_m, 4);
    }
    else
    {
        Serial.print("INVALID");
    }

    Serial.print(" SENSOR_V ");

    if (position_is_fresh())
    {
        Serial.print(position_sensor.sensor_voltage_v(), 4);
    }
    else
    {
        Serial.print("INVALID");
    }

    Serial.print(" TARGET_M ");
    Serial.print(target_position_m, 4);

    Serial.print(" GOAL_ACTIVE ");
    Serial.print(goal_active ? 1 : 0);

    Serial.print(" STATE ");
    Serial.print(task_state_name());

    Serial.print(" UNLOCKED ");
    Serial.println(is_unlocked() ? 1 : 0);
}

}  // namespace

// =============================================================================
// Arduino entry points
// =============================================================================

void setup()
{
    pinMode(kUpPin, OUTPUT);
    pinMode(kStopPin, OUTPUT);
    pinMode(kDownPin, OUTPUT);

    pinMode(kUnlockedSensePin, INPUT);

    release_all_buttons();

    Serial.begin(115200);

    if (!position_sensor.begin())
    {
        Serial.println("ERR POSITION_SENSOR_INIT");

        enter_fault("POSITION_SENSOR_INIT");
    }
    else
    {
        Serial.println("INFO POSITION_SENSOR_READY");
    }

    // The factory pedestal controller is latching. Explicitly send STOP at
    // startup in case the ESP32 reset while the controller remained powered.
    start_button_pulse(kStopPin);

    commanded_motion = CommandedMotion::kStopped;

    Serial.println("INFO PEDESTAL_READY");
}

void loop()
{
    // None of these functions should intentionally block.
    update_position_sensor();

    process_serial();

    update_button_output();

    update_task_state_machine();

    check_watchdog();

    publish_telemetry();
}