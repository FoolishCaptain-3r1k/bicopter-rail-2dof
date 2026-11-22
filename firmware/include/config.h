#pragma once

#include <cstdint>

namespace bicopter {

// I2C bus configuration
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr uint32_t I2C_FREQ_HZ = 400000;

// Sensor control pins & I2C addresses
constexpr uint8_t TOF_XSHUT_PIN = 19;
constexpr uint8_t BNO055_I2C_ADDR = 0x28;  // Requires BNO055 ADD pin tied to GND
constexpr uint8_t TOF_I2C_ADDR = 0x29;     // Default VL53L0X/VL53L1X address

// ESC PWM output pins
constexpr uint8_t ESC_LEFT_PIN = 25;
constexpr uint8_t ESC_RIGHT_PIN = 26;

// Physical & safety limits
constexpr uint32_t PWM_FREQ_HZ = 50;
constexpr uint16_t PWM_MIN_US = 1000;
constexpr uint16_t PWM_SAFE_MAX_US = 1350;
constexpr uint16_t PWM_ABS_LIMIT_US = 1500;
constexpr float ANGLE_CUTOFF_DEG = 55.0f;
constexpr float RAIL_MIN_MM = 0.0f;
constexpr float RAIL_MAX_MM = 230.0f;
constexpr uint32_t WATCHDOG_MS = 250;

// Hardware interface contracts
struct SensorState {
    float z_mm = 0.0f;
    float theta_deg = 0.0f;
    float omega_dps = 0.0f;
    bool tof_ok = false;
    bool imu_ok = false;
    uint32_t ts_ms = 0;
};

struct ControlCommand {
    uint16_t esc_left_us = PWM_MIN_US;
    uint16_t esc_right_us = PWM_MIN_US;
    bool armed = false;
};

}  // namespace bicopter
