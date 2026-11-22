#pragma once

#include <Stream.h>
#include <Adafruit_BNO055.h>
#include <VL53L0X.h>
#include <VL53L1X.h>
#include "config.h"

namespace bicopter {

/**
 * @brief Scan all 7-bit I2C addresses (0x08..0x77) and print found devices.
 */
void scanI2cBus(Stream& out);

/**
 * @brief Manages non-blocking initialization and sampling of BNO055 IMU and ToF sensor.
 */
class SensorManager {
public:
    SensorManager();

    bool begin();
    void update(SensorState& out);
    void zeroOffsets();
    TofModel getTofModel() const { return tof_model_; }

private:
    bool initImu();
    bool initTof();
    TofModel detectTofModel();
    void updateImu(SensorState& out);
    void updateTof(SensorState& out);

    Adafruit_BNO055 bno_;
    VL53L0X tof_l0_;
    VL53L1X tof_l1_;

    TofModel tof_model_ = TofModel::NONE;
    bool imu_ok_ = false;
    bool tof_ok_ = false;

    float raw_theta_deg_ = 0.0f;
    float theta_offset_deg_ = 0.0f;
    float raw_z_mm_ = 0.0f;
    float z_offset_mm_ = 0.0f;
};

}  // namespace bicopter
