#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>
#include <VL53L1X.h>

namespace {

constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint8_t TOF_ADDR = 0x29;  // 7-bit I2C address
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t I2C_HZ = 100000;
constexpr uint16_t SENSOR_TIMEOUT_MS = 100;
constexpr uint32_t SAMPLE_PERIOD_MS = 500;
constexpr uint32_t RETRY_PERIOD_MS = 2000;

enum class Model { None, L0X, L1X };

VL53L0X l0;
VL53L1X l1;
Model model = Model::None;
uint32_t last_sample_ms = 0;
uint32_t last_retry_ms = 0;

const char* modelName(Model value) {
    switch (value) {
        case Model::L0X: return "VL53L0X";
        case Model::L1X: return "VL53L1X";
        default: return "UNKNOWN";
    }
}

bool probe() {
    Wire.beginTransmission(TOF_ADDR);
    return Wire.endTransmission() == 0;
}

bool readId8(uint8_t reg, uint8_t& value) {
    Wire.beginTransmission(TOF_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0 || Wire.requestFrom(TOF_ADDR, static_cast<uint8_t>(1)) != 1) {
        return false;
    }
    value = Wire.read();
    return true;
}

bool readId16(uint16_t reg, uint8_t& value) {
    Wire.beginTransmission(TOF_ADDR);
    Wire.write(static_cast<uint8_t>(reg >> 8));
    Wire.write(static_cast<uint8_t>(reg));
    if (Wire.endTransmission(false) != 0 || Wire.requestFrom(TOF_ADDR, static_cast<uint8_t>(1)) != 1) {
        return false;
    }
    value = Wire.read();
    return true;
}

Model detectModel() {
    if (!probe()) {
        Serial.println("ERROR I2C_NO_ACK address=0x29");
        return Model::None;
    }

    uint8_t id = 0;
    if (readId8(0xC0, id) && id == 0xEE) {
        Serial.println("DETECTED model=VL53L0X id_register=0xC0 id=0xEE");
        return Model::L0X;
    }
    if (readId16(0x010F, id) && id == 0xEA) {
        Serial.println("DETECTED model=VL53L1X id_register=0x010F id=0xEA");
        return Model::L1X;
    }

    Serial.println("ERROR UNKNOWN_MODEL address=0x29 (no matching model ID; check module and wiring)");
    return Model::None;
}

bool startSensor(Model detected) {
    if (detected == Model::L0X) {
        l0.setBus(&Wire);
        l0.setTimeout(SENSOR_TIMEOUT_MS);
        if (!l0.init()) {
            Serial.println("ERROR INIT_FAILED model=VL53L0X");
            return false;
        }
        if (!l0.setMeasurementTimingBudget(50000)) {
            Serial.println("ERROR TIMING_BUDGET_FAILED model=VL53L0X");
            return false;
        }
        l0.startContinuous(50);
        return true;
    }
    if (detected == Model::L1X) {
        l1.setBus(&Wire);
        l1.setTimeout(SENSOR_TIMEOUT_MS);
        if (!l1.init()) {
            Serial.println("ERROR INIT_FAILED model=VL53L1X");
            return false;
        }
        if (!l1.setDistanceMode(VL53L1X::Short) || !l1.setMeasurementTimingBudget(50000)) {
            Serial.println("ERROR RANGING_CONFIG_FAILED model=VL53L1X");
            return false;
        }
        l1.startContinuous(50);
        return true;
    }
    return false;
}

void sample() {
    if (!probe()) {
        Serial.printf("ERROR I2C_LOST model=%s\n", modelName(model));
        model = Model::None;
        return;
    }

    uint16_t distance_mm = 0;
    if (model == Model::L0X) {
        distance_mm = l0.readRangeContinuousMillimeters();
        if (l0.timeoutOccurred()) {
            Serial.println("ERROR TIMEOUT model=VL53L0X");
            model = Model::None;
            return;
        }
        if (distance_mm >= 8190) {
            Serial.printf("ERROR INVALID_RANGE model=VL53L0X raw_mm=%u\n", distance_mm);
            return;
        }
    } else if (model == Model::L1X) {
        distance_mm = l1.read();
        if (l1.timeoutOccurred()) {
            Serial.println("ERROR TIMEOUT model=VL53L1X");
            model = Model::None;
            return;
        }
        if (l1.ranging_data.range_status != VL53L1X::RangeValid) {
            Serial.printf("ERROR INVALID_RANGE model=VL53L1X range_status=%u raw_mm=%u\n",
                          static_cast<unsigned>(l1.ranging_data.range_status), distance_mm);
            return;
        }
    } else {
        return;
    }

    Serial.printf("DATA model=%s distance_mm=%u status=OK\n", modelName(model), distance_mm);
}

}  // namespace

void setup() {
    Serial.begin(SERIAL_BAUD);
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(I2C_HZ);
    Serial.println("VL53 standalone test | ESP32 | 115200 baud");
    Serial.println("ESC/motor pins are not configured or driven by this program.");
    Serial.println("XSHUT is not driven; leave GPIO19 disconnected unless the module is verified.");
    last_retry_ms = millis() - RETRY_PERIOD_MS;
}

void loop() {
    const uint32_t now = millis();
    if (model == Model::None) {
        if (static_cast<uint32_t>(now - last_retry_ms) >= RETRY_PERIOD_MS) {
            last_retry_ms = now;
            const Model detected = detectModel();
            if (detected != Model::None && startSensor(detected)) {
                model = detected;
                last_sample_ms = now;
                Serial.printf("READY model=%s\n", modelName(model));
            }
        }
    } else if (static_cast<uint32_t>(now - last_sample_ms) >= SAMPLE_PERIOD_MS) {
        last_sample_ms = now;
        sample();
    }
    delay(5);
}
