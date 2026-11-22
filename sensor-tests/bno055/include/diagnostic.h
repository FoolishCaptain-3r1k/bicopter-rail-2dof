#pragma once
#include <Arduino.h>
#include <Wire.h>
#include "telemetry.h"

#ifndef BNO_I2C_RESTART
#define BNO_I2C_RESTART 0
#endif

namespace diagnostic {
inline bool write(uint8_t addr,uint8_t reg,uint8_t value){
    Wire.beginTransmission(addr);Wire.write(reg);Wire.write(value);
    const uint8_t result=Wire.endTransmission(true);
    if(result)Serial.printf("# I2C_FAIL reg=0x%02X phase=write_config code=%u\n",reg,result);
    return result==0;
}
inline bool configure(uint8_t addr,bool ndof){
    if(!write(addr,0x3D,0x00))return false; // CONFIGMODE
    delay(25);
    if(!write(addr,0x07,0x00)||!write(addr,0x3E,0x00)||!write(addr,0x3D,ndof?0x0C:0x08))return false;
    delay(30);
    return true;
}
inline bool read(uint8_t addr,uint8_t reg,uint8_t* out,uint8_t length){
    Wire.beginTransmission(addr);
    Wire.write(reg);
    const uint8_t tx=Wire.endTransmission(BNO_I2C_RESTART ? false : true);
    if(tx){Serial.printf("# I2C_FAIL reg=0x%02X phase=write code=%u\n",reg,tx);return false;}
    const uint8_t got=Wire.requestFrom(addr,length);
    if(got!=length){Serial.printf("# I2C_FAIL reg=0x%02X phase=read expected=%u got=%u\n",reg,length,got);return false;}
    for(uint8_t i=0;i<length;++i)out[i]=Wire.read();
    return true;
}
inline int16_t word(const uint8_t* b,int i){return static_cast<int16_t>(static_cast<uint16_t>(b[i])|(static_cast<uint16_t>(b[i+1])<<8));}
inline bool sample(uint8_t addr,ImuSample& s){
    uint8_t status[3],cal,e[6],accel[6],gyro[6],q[8];
    // Status registers are read separately to preserve their documented addresses.
    if(!read(addr,0x39,&status[0],1)||!read(addr,0x3A,&status[1],1)||!read(addr,0x3B,&status[2],1)||!read(addr,0x35,&cal,1)||
       !read(addr,0x1A,e,6)||!read(addr,0x08,accel,6)||!read(addr,0x14,gyro,6)||!read(addr,0x20,q,8)){
        Serial.println("# INVALID reason=i2c_transaction");return false;
    }
    Serial.printf("# STATUS system=%u selftest=0x%02X error=%u\n",status[0],status[1],status[2]);
    if(status[2]!=0){Serial.printf("# INVALID reason=system_error code=%u\n",status[2]);return false;}
    mapEuler(word(e,0)/16.0f,word(e,2)/16.0f,word(e,4)/16.0f,s);
    s.ax=word(accel,0)/100.0f;s.ay=word(accel,2)/100.0f;s.az=word(accel,4)/100.0f;
    s.gx=word(gyro,0)/16.0f;s.gy=word(gyro,2)/16.0f;s.gz=word(gyro,4)/16.0f;
    s.qw=word(q,0)/16384.0f;s.qx=word(q,2)/16384.0f;s.qy=word(q,4)/16384.0f;s.qz=word(q,6)/16384.0f;
    s.cal_sys=(cal>>6)&3;s.cal_gyro=(cal>>4)&3;s.cal_accel=(cal>>2)&3;s.cal_mag=cal&3;
    s.ts_ms=millis();
    const char* reason=invalidReason(s);
    const float norm=s.qw*s.qw+s.qx*s.qx+s.qy*s.qy+s.qz*s.qz;
    Serial.printf("# RAW Euler=%.2f,%.2f,%.2f accel=%.2f,%.2f,%.2f gyro=%.2f,%.2f,%.2f quat=%.4f,%.4f,%.4f,%.4f norm=%.4f\n",
        s.roll,s.pitch,s.yaw,s.ax,s.ay,s.az,s.gx,s.gy,s.gz,s.qw,s.qx,s.qy,s.qz,norm);
    if(reason){Serial.printf("# INVALID reason=%s\n",reason);return false;}
    s.valid=true;return true;
}
}
