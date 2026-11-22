#include "sensors.h"

#include <Arduino.h>
#include <Wire.h>

namespace bicopter {
namespace {

bool probeI2cDevice(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
}

bool readReg8(uint8_t addr, uint8_t reg, uint8_t& val) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) {
        return false;
    }
    if (Wire.requestFrom(addr, static_cast<uint8_t>(1)) != 1) {
        return false;
    }
    val = Wire.read();
    return true;
}

bool readReg16Addr8(uint8_t addr, uint16_t reg, uint8_t& val) {
    Wire.beginTransmission(addr);
    Wire.write(static_cast<uint8_t>((reg >> 8) & 0xFF));
    Wire.write(static_cast<uint8_t>(reg & 0xFF));
    if (Wire.endTransmission(false) != 0) {
        return false;
    }
    if (Wire.requestFrom(addr, static_cast<uint8_t>(1)) != 1) {
        return false;
    }
    val = Wire.read();
    return true;
}

void mapTiltAxis(const imu::Vector<3>& euler,
                 const imu::Vector<3>& gyro,
                 float& angle_deg,
                 float& rate_dps) {
    switch (IMU_TILT_AXIS) {
        case TiltAxis::ROLL:
            angle_deg = static_cast<float>(euler.y());
            rate_dps = static_cast<float>(gyro.x());
            break;
        case TiltAxis::PITCH:
            angle_deg = static_cast<float>(euler.z());
            rate_dps = static_cast<float>(gyro.y());
            break;
        case TiltAxis::YAW:
            angle_deg = static_cast<float>(euler.x());
            rate_dps = static_cast<float>(gyro.z());
            break;
    }
    angle_deg *= IMU_TILT_SIGN;
    rate_dps *= IMU_TILT_SIGN;
}

}  // namespace

void scanI2cBus(Stream& out) {
    out.println("[I2C] Scanning bus...");
    uint8_t found = 0;
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        if (probeI2cDevice(addr)) {
            out.printf("[I2C] Found device at 0x%02X\n", addr);
            ++found;
        }
    }
    if (found == 0) {
        out.println("[I2C] No devices found.");
    } else {
        out.printf("[I2C] Scan complete (%u device(s)).\n", found);
    }
}

SensorManager::SensorManager()
    : bno_(-1, BNO055_I2C_ADDR, &Wire) {}

bool SensorManager::begin() {
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    Wire.setClock(I2C_FREQ_HZ);

    imu_ok_ = initImu();
    tof_ok_ = initTof();
    return imu_ok_ && tof_ok_;
}

bool SensorManager::initImu() {
    if (!probeI2cDevice(BNO055_I2C_ADDR)) {
        return false;
    }
    if (!bno_.begin(OPERATION_MODE_IMUPLUS)) {
        return false;
    }
    bno_.setExtCrystalUse(true);
    return true;
}

TofModel SensorManager::detectTofModel() {
    if (!probeI2cDevice(TOF_I2C_ADDR)) {
        return TofModel::NONE;
    }
    uint8_t id = 0;
    if (readReg16Addr8(TOF_I2C_ADDR, 0x010F, id) && id == 0xEA) {
        return TofModel::VL53L1X;
    }
    if (readReg8(TOF_I2C_ADDR, 0xC0, id) && id == 0xEE) {
        return TofModel::VL53L0X;
    }
    return TofModel::NONE;
}

bool SensorManager::initTof() {
    pinMode(TOF_XSHUT_PIN, OUTPUT);
    digitalWrite(TOF_XSHUT_PIN, LOW);
    delay(10);
    digitalWrite(TOF_XSHUT_PIN, HIGH);
    delay(10);

    tof_model_ = detectTofModel();
    if (tof_model_ == TofModel::VL53L1X) {
        tof_l1_.setBus(&Wire);
        tof_l1_.setAddress(TOF_I2C_ADDR);
        tof_l1_.setTimeout(50);
        if (!tof_l1_.init()) {
            tof_model_ = TofModel::NONE;
            return false;
        }
        tof_l1_.setDistanceMode(VL53L1X::Short);
        tof_l1_.setMeasurementTimingBudget(TOF_TIMING_BUDGET_MS * 1000UL);
        tof_l1_.startContinuous(TOF_TIMING_BUDGET_MS);
        return true;
    }

    if (tof_model_ == TofModel::VL53L0X) {
        tof_l0_.setBus(&Wire);
        tof_l0_.setAddress(TOF_I2C_ADDR);
        tof_l0_.setTimeout(50);
        if (!tof_l0_.init()) {
            tof_model_ = TofModel::NONE;
            return false;
        }
        tof_l0_.setMeasurementTimingBudget(TOF_TIMING_BUDGET_MS * 1000UL);
        tof_l0_.startContinuous();
        return true;
    }

    return false;
}

void SensorManager::updateImu(SensorState& out) {
    if (!imu_ok_ || !probeI2cDevice(BNO055_I2C_ADDR)) {
        imu_ok_ = false;
        out.imu_ok = false;
        return;
    }

    const imu::Vector<3> euler = bno_.getVector(Adafruit_BNO055::VECTOR_EULER);
    const imu::Vector<3> gyro = bno_.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);

    float angle_deg = 0.0f;
    float rate_dps = 0.0f;
    mapTiltAxis(euler, gyro, angle_deg, rate_dps);

    raw_theta_deg_ = angle_deg;
    out.theta_deg = raw_theta_deg_ - theta_offset_deg_;
    out.omega_dps = rate_dps;
    out.imu_ok = true;
}

void SensorManager::updateTof(SensorState& out) {
    if (!tof_ok_) {
        out.tof_ok = false;
        return;
    }

    if (tof_model_ == TofModel::VL53L1X) {
        if (tof_l1_.dataReady()) {
            const uint16_t mm = tof_l1_.read(false);
            if (tof_l1_.timeoutOccurred()) {
                tof_ok_ = false;
                out.tof_ok = false;
                return;
            }
            if (tof_l1_.ranging_data.range_status == VL53L1X::RangeValid) {
                raw_z_mm_ = static_cast<float>(mm);
            }
        }
        out.z_mm = raw_z_mm_ - z_offset_mm_;
        out.tof_ok = true;
        return;
    }

    if (tof_model_ == TofModel::VL53L0X) {
        if ((tof_l0_.readReg(VL53L0X::RESULT_INTERRUPT_STATUS) & 0x07) != 0) {
            const uint16_t mm = tof_l0_.readRangeContinuousMillimeters();
            if (tof_l0_.timeoutOccurred()) {
                tof_ok_ = false;
                out.tof_ok = false;
                return;
            }
            if (mm < 8190) {
                raw_z_mm_ = static_cast<float>(mm);
            }
        }
        out.z_mm = raw_z_mm_ - z_offset_mm_;
        out.tof_ok = true;
        return;
    }

    out.tof_ok = false;
}

void SensorManager::update(SensorState& out) {
    out.ts_ms = millis();
    updateImu(out);
    updateTof(out);
}

void SensorManager::zeroOffsets() {
    theta_offset_deg_ = raw_theta_deg_;
    z_offset_mm_ = raw_z_mm_;
}

}  // namespace bicopter
