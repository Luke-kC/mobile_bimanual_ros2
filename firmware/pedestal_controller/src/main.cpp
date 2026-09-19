#include <Arduino.h>

namespace
{
constexpr gpio_num_t kUpPin = GPIO_NUM_21;
constexpr gpio_num_t kStopPin = GPIO_NUM_22;
constexpr gpio_num_t kDownPin = GPIO_NUM_23;
constexpr gpio_num_t kUnlockedSensePin = GPIO_NUM_19;

constexpr uint32_t kPulseDurationMs = 200;
constexpr uint32_t kHeartbeatTimeoutMs = 500;
constexpr uint32_t kDirectionChangeDelayMs = 500;
constexpr uint32_t kUnlockSettleDelayMs = 500;
constexpr uint32_t kUnlockTimeoutMs = 7000;

enum class CommandedMotion
{
    kStopped,
    kUp,
    kDown,
};

CommandedMotion commanded_motion = CommandedMotion::kStopped;
uint32_t last_heartbeat_ms = 0;

bool is_unlocked();

void pulse(const gpio_num_t pin)
{
    digitalWrite(pin, HIGH);
    delay(kPulseDurationMs);
    digitalWrite(pin, LOW);
}

void stop_motion()
{
    pulse(kStopPin);
    commanded_motion = CommandedMotion::kStopped;
}

void command_stop()
{
    stop_motion();
    Serial.println("OK STOP");
}

void command_up()
{
    if (!is_unlocked())
    {
        Serial.println("ERR LOCKED");
        return;
    }

    if (commanded_motion == CommandedMotion::kDown)
    {
        command_stop();
        delay(kDirectionChangeDelayMs);
    }

    if (commanded_motion != CommandedMotion::kUp)
    {
        pulse(kUpPin);
        commanded_motion = CommandedMotion::kUp;
    }

    last_heartbeat_ms = millis();

    Serial.println("OK UP");
}

void command_down()
{
    if (!is_unlocked())
    {
        Serial.println("ERR LOCKED");
        return;
    }

    if (commanded_motion == CommandedMotion::kUp)
    {
        command_stop();
        delay(kDirectionChangeDelayMs);
    }

    if (commanded_motion != CommandedMotion::kDown)
    {
        pulse(kDownPin);
        commanded_motion = CommandedMotion::kDown;
    }

    last_heartbeat_ms = millis();

    Serial.println("OK DOWN");
}

void command_unlock()
{
    if (commanded_motion != CommandedMotion::kStopped)
    {
        Serial.println("ERR UNLOCK WHILE MOVING");
        return;
    }

    if (is_unlocked())
    {
        Serial.println("ALREADY UNLOCKED");
        return;
    }

    Serial.println("UNLOCKING...");

    const uint32_t start_ms = millis();

    digitalWrite(kDownPin, HIGH);

    while (!is_unlocked())
    {
        if (millis() - start_ms > kUnlockTimeoutMs)
        {
            digitalWrite(kDownPin, LOW);
            Serial.println("ERR UNLOCK TIMEOUT");
            return;
        }
        delay(1);
    }

    digitalWrite(kDownPin, LOW);

    delay(kUnlockSettleDelayMs);

    if (!is_unlocked())
    {
        Serial.println("ERR UNLOCK FAILED");
        return;
    }

    Serial.println("OK UNLOCK");
}

void heartbeat()
{
    if (commanded_motion != CommandedMotion::kStopped)
    {
        last_heartbeat_ms = millis();
    }

    Serial.println("OK HEARTBEAT");
}

void check_watchdog()
{
    if (commanded_motion == CommandedMotion::kStopped)
    {
        return;
    }

    if (millis() - last_heartbeat_ms > kHeartbeatTimeoutMs)
    {
        stop_motion();
        Serial.println("WATCHDOG STOP");
    }
}

bool is_unlocked() { return digitalRead(kUnlockedSensePin) == LOW; }

}  // namespace

void setup()
{
    pinMode(kUpPin, OUTPUT);
    pinMode(kStopPin, OUTPUT);
    pinMode(kDownPin, OUTPUT);

    pinMode(kUnlockedSensePin, INPUT);

    digitalWrite(kUpPin, LOW);
    digitalWrite(kStopPin, LOW);
    digitalWrite(kDownPin, LOW);

    Serial.begin(115200);

    command_stop();
}

void loop()
{
    check_watchdog();

    if (Serial.available() <= 0)
    {
        return;
    }

    switch (static_cast<char>(Serial.read()))
    {
        case 'u':
            command_up();
            break;

        case 's':
            command_stop();
            break;

        case 'd':
            command_down();
            break;

        case 'h':
            heartbeat();
            break;

        case 'l':
            command_unlock();
            break;

        default:
            break;
    }
}
