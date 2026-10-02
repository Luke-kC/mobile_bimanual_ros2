#include <Arduino.h>

constexpr int kPositionPin = 34;

constexpr int kSampleCount = 16;
constexpr uint32_t kLoopPeriodMs = 20;  // 50 Hz
constexpr float kFilterAlpha = 0.10F;
constexpr float kDividerScale = 2.4706F;  // 10k / 6.8k divider

float filtered_adc_v = 0.0F;
bool filter_initialized = false;

void setup()
{
    Serial.begin(115200);

    analogReadResolution(12);
    analogSetPinAttenuation(kPositionPin, ADC_6db);
}

void loop()
{
    uint32_t raw_sum = 0;
    uint32_t adc_mv_sum = 0;

    for (int i = 0; i < kSampleCount; ++i)
    {
        raw_sum += analogRead(kPositionPin);
        adc_mv_sum += analogReadMilliVolts(kPositionPin);
        delayMicroseconds(200);
    }

    const int raw = raw_sum / kSampleCount;
    const float adc_v = (adc_mv_sum / static_cast<float>(kSampleCount)) / 1000.0F;

    if (!filter_initialized)
    {
        filtered_adc_v = adc_v;
        filter_initialized = true;
    }
    else
    {
        filtered_adc_v += kFilterAlpha * (adc_v - filtered_adc_v);
    }

    const float sensor_v = adc_v * kDividerScale;
    const float filtered_sensor_v = filtered_adc_v * kDividerScale;

    Serial.printf("raw=%d adc=%.3fV sensor=%.3fV filtered=%.3fV\n",
                  raw,
                  adc_v,
                  sensor_v,
                  filtered_sensor_v);

    delay(kLoopPeriodMs);
}
