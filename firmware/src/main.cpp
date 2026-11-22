#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "sensors.h"

namespace {

bicopter::SensorManager g_sensors;
bicopter::SensorState g_sensor_state{};
bicopter::ControlCommand g_control_cmd{};

uint32_t g_last_sensor_ms = 0;
uint32_t g_last_telemetry_ms = 0;

constexpr uint32_t SENSOR_PERIOD_MS = 1000UL / bicopter::SENSOR_LOOP_HZ;
constexpr uint32_t TELEMETRY_PERIOD_MS = 1000UL / bicopter::TELEMETRY_HZ;

const char* tofModelToStr(bicopter::TofModel model) {
    switch (model) {
        case bicopter::TofModel::VL53L0X:
            return "VL53L0X";
        case bicopter::TofModel::VL53L1X:
            return "VL53L1X";
        case bicopter::TofModel::NONE:
        default:
            return "NONE";
    }
}

void handleSerialCommands() {
    while (Serial.available() > 0) {
        const int ch = Serial.read();
        if (ch == 'z' || ch == 'Z') {
            g_sensors.zeroOffsets();
            Serial.println("# [CMD] Zero offsets applied.");
        } else if (ch == 's' || ch == 'S') {
            bicopter::scanI2cBus(Serial);
        }
    }
}

}  // namespace

void setup() {
    // Keep ESC pins strictly inactive/LOW during sensor phase
    pinMode(bicopter::ESC_LEFT_PIN, OUTPUT);
    pinMode(bicopter::ESC_RIGHT_PIN, OUTPUT);
    digitalWrite(bicopter::ESC_LEFT_PIN, LOW);
    digitalWrite(bicopter::ESC_RIGHT_PIN, LOW);

    g_control_cmd.armed = false;
    g_control_cmd.esc_left_us = bicopter::PWM_MIN_US;
    g_control_cmd.esc_right_us = bicopter::PWM_MIN_US;

    Serial.begin(115200);
    delay(200);

    Wire.begin(bicopter::I2C_SDA_PIN, bicopter::I2C_SCL_PIN);
    Wire.setClock(bicopter::I2C_FREQ_HZ);

    Serial.println("========================================");
    Serial.println(" Bicopter Rail 2-DOF | Sensor Telemetry");
    Serial.println("========================================");
    bicopter::scanI2cBus(Serial);

    g_sensors.begin();
    g_sensors.update(g_sensor_state);

    Serial.printf("# ToF Model: %s | tof_ok=%d | imu_ok=%d\n",
                  tofModelToStr(g_sensors.getTofModel()),
                  g_sensor_state.tof_ok ? 1 : 0,
                  g_sensor_state.imu_ok ? 1 : 0);
    Serial.println("# Commands: 'z' = zeroOffsets, 's' = scanI2cBus");
    Serial.println("ts_ms,z_mm,theta_deg,omega_dps,tof_ok,imu_ok");

    const uint32_t now = millis();
    g_last_sensor_ms = now;
    g_last_telemetry_ms = now;
}

void loop() {
    handleSerialCommands();

    const uint32_t now = millis();
    if (static_cast<uint32_t>(now - g_last_sensor_ms) >= SENSOR_PERIOD_MS) {
        g_last_sensor_ms = now;
        g_sensors.update(g_sensor_state);
    }

    if (static_cast<uint32_t>(now - g_last_telemetry_ms) >= TELEMETRY_PERIOD_MS) {
        g_last_telemetry_ms = now;
        Serial.printf("%lu,%.2f,%.2f,%.2f,%d,%d\n",
                      static_cast<unsigned long>(g_sensor_state.ts_ms),
                      g_sensor_state.z_mm,
                      g_sensor_state.theta_deg,
                      g_sensor_state.omega_dps,
                      g_sensor_state.tof_ok ? 1 : 0,
                      g_sensor_state.imu_ok ? 1 : 0);
    }
}
