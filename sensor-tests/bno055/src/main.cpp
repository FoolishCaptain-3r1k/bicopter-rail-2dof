#include <Arduino.h>
#include <Wire.h>
#include "telemetry.h"
#include "diagnostic.h"

namespace {
constexpr uint8_t SDA_PIN=21, SCL_PIN=22;
constexpr uint32_t SAMPLE_MS=100, RETRY_MS=2000;
constexpr uint32_t I2C_HZ=100000;
constexpr uint16_t I2C_TIMEOUT_MS=50;
ImuSample latest;
bool connected=false;
uint8_t activeAddress=0;
uint32_t lastAttempt=0, lastPoll=0, lastSerial=0, serialSeq=0;

bool initialize() {
    for (uint8_t addr : {uint8_t(0x28), uint8_t(0x29)}) {
        uint8_t id=0;
        if (!diagnostic::read(addr,0x00,&id,1)) continue;
        Serial.printf("# CHIP address=0x%02X id=0x%02X\n",addr,id);
        if (id!=0xA0) continue;
        if (!diagnostic::configure(addr,false)) {
            Serial.println("# INVALID reason=mode_config");
            continue;
        }
        activeAddress=addr;
        latest.valid=false;
        connected=true;
        Serial.printf("# BNO055 I2C=0x%02X mode=IMUPLUS\n",addr);
        return true;
    }
    Serial.println("# ERROR BNO055 not initialized at 0x28/0x29");
    return false;
}

void acquire() {
    ImuSample s;
    const auto result=diagnostic::sample(activeAddress,s);
    if (result!=diagnostic::SampleResult::Valid) {
        latest.valid=false;
        if (result==diagnostic::SampleResult::CommunicationFailure) {
            connected=false;
            lastAttempt=millis();
        }
        return;
    }
    s.hz=latest.seq ? 1000.0f/static_cast<float>(s.ts_ms-latest.ts_ms) : 0;
    s.seq=latest.seq+1;
    latest=s;
}
}

void setup() {
    Serial.begin(115200);
    // Let the sensor boot before the first I2C access; reset has a separate wait.
    delay(700);
    Wire.begin(SDA_PIN,SCL_PIN);
    Wire.setClock(I2C_HZ);
    Wire.setTimeOut(I2C_TIMEOUT_MS);
    Serial.printf("# BNO055 USB_ONLY mode=IMUPLUS I2C=%lu timeout_ms=%u STOP_between_register_and_read=%d\n",
        static_cast<unsigned long>(Wire.getClock()),I2C_TIMEOUT_MS,!BNO_I2C_RESTART);
    Serial.println("ts_ms,roll_deg,pitch_deg,yaw_deg,gx_dps,gy_dps,gz_dps,ax_ms2,ay_ms2,az_ms2,cal_sys,cal_gyro,cal_accel,cal_mag,status");
    lastAttempt=millis()-RETRY_MS;
}

void loop() {
    uint32_t now=millis();
    if (!connected && static_cast<uint32_t>(now-lastAttempt)>=RETRY_MS) {
        lastAttempt=now;
        initialize();
    }
    now=millis();
    if (connected && static_cast<uint32_t>(now-lastPoll)>=SAMPLE_MS) {
        lastPoll=now;
        acquire();
    }
    now=millis();
    if (static_cast<uint32_t>(now-lastSerial)>=SAMPLE_MS) {
        lastSerial=now;
        char line[220];
        const bool ok=connected && fresh(latest,now) && latest.seq!=serialSeq;
        if (ok) serialSeq=latest.seq;
        csvLine(line,sizeof(line),latest,ok);
        Serial.print(line);
    }
    delay(1);
}
