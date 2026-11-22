#include <Arduino.h>
#include "config.h"

namespace {

bicopter::SensorState g_sensor_state{};
bicopter::ControlCommand g_control_cmd{};

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(200);

    // Ensure safe boot state: disarmed, minimum throttle, no PWM output attached yet
    g_control_cmd.armed = false;
    g_control_cmd.esc_left_us = bicopter::PWM_MIN_US;
    g_control_cmd.esc_right_us = bicopter::PWM_MIN_US;

    Serial.println("========================================");
    Serial.println(" Bicopter Rail 2-DOF | Firmware Stub");
    Serial.println("========================================");
    Serial.printf("Armed      : %s\n", g_control_cmd.armed ? "TRUE" : "FALSE");
    Serial.printf("ESC L / R  : %u us / %u us\n",
                  g_control_cmd.esc_left_us,
                  g_control_cmd.esc_right_us);
    Serial.printf("PWM Limits : min=%u safe_max=%u abs=%u Hz=%lu\n",
                  bicopter::PWM_MIN_US,
                  bicopter::PWM_SAFE_MAX_US,
                  bicopter::PWM_ABS_LIMIT_US,
                  static_cast<unsigned long>(bicopter::PWM_FREQ_HZ));
    Serial.printf("I2C        : SDA=%u SCL=%u @ %lu Hz (IMU=0x%02X, ToF=0x%02X)\n",
                  bicopter::I2C_SDA_PIN,
                  bicopter::I2C_SCL_PIN,
                  static_cast<unsigned long>(bicopter::I2C_FREQ_HZ),
                  bicopter::BNO055_I2C_ADDR,
                  bicopter::TOF_I2C_ADDR);
    Serial.println("Status     : SAFE IDLE (motors not energized)");
}

void loop() {
    (void)g_sensor_state;
    delay(1000);
}
