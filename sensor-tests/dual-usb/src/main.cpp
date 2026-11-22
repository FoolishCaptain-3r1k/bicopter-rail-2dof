#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>
#include "diagnostic.h"

namespace {
constexpr uint8_t IMU_ADDR=0x28, TOF_ADDR=0x29;
constexpr uint32_t IMU_MS=100, TOF_MS=500, RETRY_MS=2000;
VL53L0X tof;
bool imuReady=false, tofReady=false;
uint32_t imuAttempt=0, tofAttempt=0, imuPoll=0, tofPoll=0, tofLastReady=0;

// Every direct transaction checks both the write result and received length.
bool tofRead(uint8_t reg,uint8_t* data,uint8_t count) {
    Wire.beginTransmission(TOF_ADDR);Wire.write(reg);
    const uint8_t tx=Wire.endTransmission(true);
    if(tx){Serial.printf("# TOF I2C_FAIL reg=0x%02X phase=write code=%u\n",reg,tx);return false;}
    const uint8_t got=Wire.requestFrom(TOF_ADDR,count);
    if(got!=count){Serial.printf("# TOF I2C_FAIL reg=0x%02X phase=read expected=%u got=%u\n",reg,count,got);return false;}
    for(uint8_t i=0;i<count;++i)data[i]=Wire.read();
    return true;
}
bool tofClear() {
    Wire.beginTransmission(TOF_ADDR);Wire.write(uint8_t(0x0B));Wire.write(uint8_t(1));
    const uint8_t result=Wire.endTransmission(true);
    if(result)Serial.printf("# TOF I2C_FAIL phase=clear code=%u\n",result);
    return result==0;
}
void tofInvalid(const char* reason) {
    Serial.printf("TOF,%lu,NA,%s,NA\n",static_cast<unsigned long>(millis()),reason);
}
void initImu() {
    imuAttempt=millis();uint8_t id=0;
    if(!diagnostic::read(IMU_ADDR,0x00,&id,1)||id!=0xA0) {
        Serial.println("# BNO ERROR expected BNO055 at 0x28; connect ADD to GND");return;
    }
    imuReady=diagnostic::configure(IMU_ADDR,false);
    Serial.printf("# BNO chip=0x%02X address=0x28 init=%s\n",id,imuReady?"OK":"FAIL");
}
void initTof() {
    tofAttempt=millis();uint8_t id=0;
    // Never initialize an unrecognized device (including a BNO055 at 0x29).
    if(!tofRead(0xC0,&id,1)||id!=0xEE) {
        Serial.printf("# TOF ERROR expected VL53L0X id=0xEE at 0x29 got=0x%02X\n",id);
        tofInvalid("MODEL_OR_I2C");return;
    }
    tof.setBus(&Wire);tof.setTimeout(100);
    if(!tof.init()||!tof.setMeasurementTimingBudget(50000)) {
        Serial.println("# TOF ERROR initialization/timing budget");tofInvalid("INIT_FAIL");return;
    }
    tof.startContinuous(50);
    if(tof.last_status!=0){tofInvalid("I2C_FAIL");return;}
    tofReady=true;tofLastReady=millis();
    Serial.println("# TOF model=VL53L0X address=0x29 budget_us=50000 output_ms=500 init=OK");
}
void sampleImu() {
    ImuSample s;
    if(imuReady) {
        const auto result=diagnostic::sample(IMU_ADDR,s,false);
        if(result==diagnostic::SampleResult::CommunicationFailure){imuReady=false;imuAttempt=millis();}
    }
    // One record per acquisition, with its own status. No cached sample is republished.
    s.ts_ms=millis();char line[220];csvLine(line,sizeof(line),s,s.valid);
    Serial.print("IMU,");Serial.print(line);
}
void sampleTof() {
    if(!tofReady){tofInvalid("DISCONNECTED");return;}
    uint8_t ready=0,frame[12];
    if(!tofRead(0x13,&ready,1)) {
        tofReady=false;tofAttempt=millis();tofInvalid("I2C_FAIL");return;
    }
    if(!(ready&7)) {
        if(static_cast<uint32_t>(millis()-tofLastReady)>1500) {
            tofReady=false;tofAttempt=millis();tofInvalid("TIMEOUT");
        }else tofInvalid("NOT_READY");
        return;
    }
    if(!tofRead(0x14,frame,sizeof(frame))||!tofClear()) {
        tofReady=false;tofAttempt=millis();tofInvalid("I2C_FAIL");return;
    }
    tofLastReady=millis();
    const uint16_t mm=(static_cast<uint16_t>(frame[10])<<8)|frame[11];
    const uint8_t deviceStatus=(frame[0]&0x78)>>3;
    // Conservative hardware-status check; not ST's full PAL sigma/signal validation.
    if(mm>=8190||deviceStatus!=11) {
        Serial.printf("TOF,%lu,NA,INVALID_RANGE,%u\n",static_cast<unsigned long>(millis()),deviceStatus);return;
    }
    Serial.printf("TOF,%lu,%u,OK,%u\n",static_cast<unsigned long>(millis()),mm,deviceStatus);
}
}

void setup() {
    Serial.begin(115200);delay(700);
    Wire.begin(21,22);Wire.setClock(100000);Wire.setTimeOut(50);
    Serial.println("# DUAL_USB v1 BNO055=0x28 VL53L0X=0x29 I2C_HZ=100000 timeout_ms=50");
    Serial.println("# IMU,ts_ms,roll,pitch,yaw,gx,gy,gz,ax,ay,az,cal_sys,cal_gyro,cal_accel,cal_mag,status");
    Serial.println("# TOF,ts_ms,distance_mm,status,device_status_raw");
    imuAttempt=tofAttempt=millis()-RETRY_MS;
}
void loop() {
    uint32_t now=millis();
    if(!imuReady&&static_cast<uint32_t>(now-imuAttempt)>=RETRY_MS)initImu();
    now=millis();
    if(!tofReady&&static_cast<uint32_t>(now-tofAttempt)>=RETRY_MS)initTof();
    now=millis();
    if(static_cast<uint32_t>(now-imuPoll)>=IMU_MS){imuPoll=now;sampleImu();}
    now=millis();
    if(static_cast<uint32_t>(now-tofPoll)>=TOF_MS){tofPoll=now;sampleTof();}
    delay(1);
}
