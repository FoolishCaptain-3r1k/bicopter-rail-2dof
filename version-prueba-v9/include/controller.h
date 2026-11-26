#pragma once
#include <Arduino.h>
#include <cmath>
#include <cstring>
#include "telemetry.h"

namespace control {
// Mounting: range decreases when rising. BNO roll and motor differential
// polarity MUST match the physical assembly. Change these together if needed.
constexpr float HEIGHT_SIGN=-1, ANGLE_SIGN=1, MIX_SIGN=1;
// User-measured calibration: a raw displacement of 9 corresponds to 90 physical mm.
constexpr float HEIGHT_SCALE = 10;
constexpr bool USE_ROLL=true;
constexpr float MIN_US=1000, FULL_US=2000, MAX_PERCENT=99;
constexpr float START_PERCENT = 45; // 1450 us
constexpr float START_RATE = 45; // percentage points/s, 1000 -> 1450 us in 1 s
constexpr float CONTROL_RATE = 20; // 200 us/s for each motor
constexpr float BASE_PERCENT = 58;
constexpr float TOF_LPF_ALPHA = 0.30f;
constexpr float ANGLE_LPF_ALPHA = 0.70f;
constexpr float HEIGHT_DEADBAND_MM = 2.0f;

// Selectable ToF low-pass filter bank (applied after median3 on deltaMm = mmMed - origin):
// 0 = EMA (alpha=0.30), 1 = SMA (N=5), 2 = Butter2 (1.5 Hz, WINNER), 3 = Bessel2 (2.0 Hz), 4 = Cheby1-2 (1.8 Hz, unity DC)
#ifndef DSP_FILTER_MODE
#define DSP_FILTER_MODE 2
#endif

struct Biquad {
    float b0, b1, b2, a1, a2;
    float z1 = 0.0f, z2 = 0.0f;
    Biquad(float b0_, float b1_, float b2_, float a1_, float a2_)
        : b0(b0_), b1(b1_), b2(b2_), a1(a1_), a2(a2_) {}
    void reset() { z1 = 0.0f; z2 = 0.0f; }
    float step(float x) {
        const float y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        return y;
    }
};
struct PID {
    float kp=0,ki=0,kd=0,integral=0;
    float step(float error,float rate,float dt) {
        const float candidate=constrain(integral+ki*error*dt,-40.0f,40.0f);
        const float raw=kp*error+candidate-kd*rate;
        if (fabsf(raw)<40 || raw*error<0) integral=candidate;
        return constrain(kp*error+integral-kd*rate,-40.0f,40.0f);
    }
};
enum class Mode { Manual, Auto };
Mode mode = Mode::Manual;
PID heightPid,anglePid;
ImuSample imu;
bool imuValid=false,tofValid=false,originReady=false,armed=false;
uint32_t imuTime=0,tofTime=0,lastHB=0,lastTick=0;
float height=0,previousHeight=0,velocity=0,origin=0,target=0,angleTarget=0;
float previousAngle=0,angularVelocity=0;
float left=0,right=0,originSum=0,originMin=1e6,originMax=0;
enum class Power { Off, Ramp, Standby, PID, Down };
Power power = Power::Off;
float angleOrigin=0;
bool angleOriginReady=false;
float angleFiltered=0;
bool angleFilterReady=false;
float tofWindow[3]={0,0,0};
unsigned tofWindowCount=0,tofWindowIdx=0;
float tofFilteredDeltaMm=0;
bool tofFilterReady=false;
int filterMode = DSP_FILTER_MODE;
float smaBuf[5]={0,0,0,0,0};
unsigned smaCount=0,smaIdx=0;
Biquad biquadButter2{0.04125354f, 0.08250707f, 0.04125354f, -1.34896775f, 0.51398189f}; // Butter2 fc=1.5Hz @ 20Hz
Biquad biquadBessel2{0.06327976f, 0.12655953f, 0.06327976f, -1.07222953f, 0.32534858f}; // Bessel2 fc=2.0Hz @ 20Hz
Biquad biquadCheby2{0.08298522f, 0.16597045f, 0.08298522f, -1.13091303f, 0.46285393f};  // Cheby1-2 fc=1.8Hz 0.5dB (unity DC) @ 20Hz
void resetTofFilters() {
    tofFilteredDeltaMm = 0.0f;
    smaCount = 0; smaIdx = 0;
    biquadButter2.reset();
    biquadBessel2.reset();
    biquadCheby2.reset();
}
unsigned originCount=0;
char line[160];size_t length=0;bool overflow=false;
float median3(float a, float b, float c) {
    if (a > b) { const float t = a; a = b; b = t; }
    if (b > c) { const float t = b; b = c; c = t; }
    if (a > b) { const float t = a; a = b; b = t; }
    return b;
}
float rawAngle(){return ANGLE_SIGN*(USE_ROLL?imu.roll:imu.pitch);}
float angle(){return (angleFilterReady ? angleFiltered : rawAngle()) - (angleOriginReady ? angleOrigin : 0);}
void updateImu(const ImuSample& s) {
    imu = s;
    imuTime = millis();
    const float raw = rawAngle();
    if (!angleFilterReady) {
        angleFiltered = raw;
        angleFilterReady = true;
    } else {
        angleFiltered = ANGLE_LPF_ALPHA * raw + (1.0f - ANGLE_LPF_ALPHA) * angleFiltered;
    }
}
const char* powerName() {
    switch (power) {
        case Power::Ramp: return "RAMP";
        case Power::Standby: return "READY";
        case Power::PID: return "PID";
        case Power::Down: return "DOWN";
        default: return "OFF";
    }
}
uint32_t pulseCounts(float percent) {
    const float pulseUs = MIN_US + (FULL_US - MIN_US) * percent / 100;
    return uint32_t(ceilf(pulseUs * 65536 / 20000)); // round up to the next 16-bit PWM count
}
void writeOutputs(float l,float r){
    left=constrain(l,0.0f,MAX_PERCENT);right=constrain(r,0.0f,MAX_PERCENT);
    ledcWrite(0,pulseCounts(left));
    ledcWrite(1,pulseCounts(right));
}
float approach(float current, float goal, float step) {
    return current + constrain(goal-current, -step, step);
}
void gradualOutputs(float l, float r, float rate, float dt) {
    writeOutputs(approach(left, constrain(l,0.0f,MAX_PERCENT),rate*dt),
                 approach(right,constrain(r,0.0f,MAX_PERCENT),rate*dt));
}
void stop(const char* reason){
    power=Power::Off;
    armed=false;heightPid.integral=anglePid.integral=0;target=angleTarget=0;
    writeOutputs(0,0);Serial.printf("STATE,STOP,%s\n",reason);
}
void setup(){
    ledcSetup(0,50,16);ledcSetup(1,50,16);
    ledcAttachPin(25,0);ledcAttachPin(26,1);writeOutputs(0,0);
}
void distance(float mm){
    tofValid=true;tofTime=millis();
    tofWindow[tofWindowIdx]=mm;
    tofWindowIdx=(tofWindowIdx+1)%3;
    if(tofWindowCount<3)++tofWindowCount;
    const float mmMed=tofWindowCount<3?mm:median3(tofWindow[0],tofWindow[1],tofWindow[2]);
    if(!originReady){
        originMin=fminf(originMin,mmMed);originMax=fmaxf(originMax,mmMed);
        if(originMax-originMin>10){originCount=0;originSum=0;originMin=originMax=mmMed;}
        originSum+=mmMed;
        if(++originCount>=30){
            origin=originSum/originCount;
            resetTofFilters();
            tofFilterReady=true;
            originReady=true;
            Serial.println("STATE,READY");
        }
    } else {
        const float deltaMm = mmMed - origin;
        if(!tofFilterReady){
            tofFilteredDeltaMm=deltaMm;
            tofFilterReady=true;
        } else {
            switch (filterMode) {
                case 1: {
                    smaBuf[smaIdx]=deltaMm;
                    smaIdx=(smaIdx+1)%5;
                    if(smaCount<5)++smaCount;
                    float sum=0.0f;
                    for(unsigned i=0;i<smaCount;++i)sum+=smaBuf[i];
                    tofFilteredDeltaMm=sum/smaCount;
                    break;
                }
                case 2:
                    tofFilteredDeltaMm=biquadButter2.step(deltaMm);
                    break;
                case 3:
                    tofFilteredDeltaMm=biquadBessel2.step(deltaMm);
                    break;
                case 4:
                    tofFilteredDeltaMm=biquadCheby2.step(deltaMm);
                    break;
                default:
                    tofFilteredDeltaMm=TOF_LPF_ALPHA*deltaMm+(1.0f-TOF_LPF_ALPHA)*tofFilteredDeltaMm;
                    break;
            }
        }
    }
    if(originReady)height=HEIGHT_SIGN*HEIGHT_SCALE*tofFilteredDeltaMm;
}
bool fresh(){return originReady&&imuValid&&tofValid&&millis()-imuTime<200&&millis()-tofTime<200;}
bool checkRunningLimits(uint32_t now) {
    if (!fresh()) {
        stop("SENSOR_INVALID_OR_STALE");
        return false;
    }
    if (now-lastHB > 350) {
        stop("LINK_TIMEOUT");
        return false;
    }
    return true;
}
bool inRange(float value, float low, float high) {
    return std::isfinite(value) && value >= low && value <= high;
}
bool validTarget(float h, float a) {
    return std::isfinite(h) && std::isfinite(a);
}
bool validGains(const PID& pid) {
    return inRange(pid.kp, 0, 100) && inRange(pid.ki, 0, 100) && inRange(pid.kd, 0, 100);
}
void start(Mode requested, float h, float a, const PID& hGains, const PID& aGains) {
    if (armed) { Serial.println("ERR,ALREADY_ARMED"); return; }
    if (!fresh()) { Serial.println("ERR,ARM_SENSORS"); return; }
    if (requested == Mode::Auto && h == 0) { Serial.println("ERR,AUTO_ZERO"); return; }
    if (!validTarget(h, a) || !validGains(hGains) || !validGains(aGains) ||
        hGains.kp <= 0 || aGains.kp <= 0 || (requested == Mode::Manual && (h != 0 || a != 0))) {
        Serial.println("ERR,ARM_CONFIG_OR_SENSORS");
        return;
    }
    lastHB = millis();
    if (!checkRunningLimits(lastHB)) return;
    heightPid = hGains;
    anglePid = aGains;
    heightPid.integral = anglePid.integral = 0;
    mode = requested;
    target = h;
    angleTarget = a;
    angleOrigin = angleFilterReady ? angleFiltered : rawAngle();
    angleOriginReady = true;
    previousHeight = height;
    previousAngle = angle();
    angularVelocity = velocity = 0;
    lastTick = lastHB;
    armed = true;
    power = Power::Ramp;
    Serial.println("STATE,ARMED");
}
void command(){
    if(!strcmp(line,"STOP")){stop("USER");return;}
    if(!strcmp(line,"HB")){lastHB=millis();return;}
    if(!strcmp(line,"ARM")){
        start(Mode::Manual, 0, 0, heightPid, anglePid);
        return;
    }
    char extra;
    float h, a;
    if (!strncmp(line, "START,", 6)) {
        char name[7];
        PID hp, ap;
        if (sscanf(line, "START,%6[^,],%f,%f,%f,%f,%f,%f,%f,%f %c", name, &h, &a,
                   &hp.kp, &hp.ki, &hp.kd, &ap.kp, &ap.ki, &ap.kd, &extra) != 9 ||
            (strcmp(name, "MANUAL") && strcmp(name, "AUTO"))) {
            Serial.println("ERR,CONFIG");
            return;
        }
        start(strcmp(name, "AUTO") == 0 ? Mode::Auto : Mode::Manual, h, a, hp, ap);
        return;
    }
    if (!strncmp(line, "TARGET,", 7)) {
        if (!armed || mode != Mode::Auto ||
            sscanf(line, "TARGET,%f,%f %c", &h, &a, &extra) != 2 || !validTarget(h, a)) {
            Serial.println("ERR,TARGET");
            return;
        }
        if (h == 0) power = Power::Down;
        target = h;
        angleTarget = a;
        Serial.println("ACK,TARGET");
        return;
    }
    if(!strcmp(line,"U")||!strcmp(line,"D")||!strcmp(line,"L")||!strcmp(line,"R")){
        if(!armed){Serial.println("ERR,DISARMED");return;}
        if(mode != Mode::Manual){Serial.println("ERR,MODE");return;}
        if(line[0]=='U')target+=10;
        if(line[0]=='D'){
            target-=10;
            if (target == 0) power = Power::Down;
        }
        if(line[0]=='L')angleTarget-=1;
        if(line[0]=='R')angleTarget+=1;
        lastHB=millis();return;
    }
    char axis;float p,i,d;
    if(sscanf(line,"PID,%c,%f,%f,%f %c",&axis,&p,&i,&d,&extra)==4&&!armed&&
       (axis=='H'||axis=='A')&&std::isfinite(p)&&std::isfinite(i)&&std::isfinite(d)&&p>=0&&i>=0&&d>=0&&p<=100&&i<=100&&d<=100){
        PID& pid=axis=='H'?heightPid:anglePid;pid.kp=p;pid.ki=i;pid.kd=d;pid.integral=0;Serial.println("ACK,PID");return;
    }
    int fmode = -1;
    if(sscanf(line,"FILTER,%d %c",&fmode,&extra)==1 && !armed && fmode>=0 && fmode<=4){
        filterMode=fmode;
        resetTofFilters();
        Serial.printf("ACK,FILTER,%d\n",filterMode);
        return;
    }
    Serial.println("ERR,COMMAND");
}
void commands(){
    for(unsigned n=0;n<256&&Serial.available();++n){
        char c=Serial.read();if(c=='\r')continue;
        if(c=='\n'){line[length]=0;if(!overflow&&length)command();else if(overflow)stop("LINE_OVERFLOW");length=0;overflow=false;}
        else if(length<sizeof(line)-1&&!overflow)line[length++]=c;else overflow=true;
    }
}
void tick(){
    const uint32_t now=millis();
    if (armed) checkRunningLimits(now);
    if(now-lastTick<50)return;
    const float dt=lastTick? (now-lastTick)/1000.0f:0.05f;lastTick=now;
    velocity=0.7f*velocity+0.3f*(height-previousHeight)/dt;previousHeight=height;
    // Differentiate the same Euler coordinate used for angular feedback.
    angularVelocity=0.7f*angularVelocity+0.3f*(angle()-previousAngle)/dt;
    previousAngle=angle();
    // Bound slew increments even if an acquisition delays the control task.
    const float outputDt = fminf(dt, 0.05f);
    if (armed && power == Power::Off && target != 0) power = Power::Ramp;
    if (armed && power == Power::Standby && target != 0) power = Power::PID;
    if (armed && power == Power::PID && target == 0) power = Power::Down;
    if (armed && power == Power::Down && target != 0) power = Power::PID;
    if (armed && power == Power::Ramp) {
        gradualOutputs(START_PERCENT, START_PERCENT, START_RATE, outputDt);
        if (left == START_PERCENT && right == START_PERCENT)
            power = target != 0 ? Power::PID : Power::Standby;
    } else if (armed && power == Power::Standby) {
        gradualOutputs(START_PERCENT, START_PERCENT, CONTROL_RATE, outputDt);
    } else if (armed && power == Power::Down) {
        heightPid.integral = anglePid.integral = 0;
        gradualOutputs(0, 0, CONTROL_RATE, outputDt);
        if (left == 0 && right == 0) power = Power::Off;
    } else if(armed&&power == Power::PID){
        const float oldH=heightPid.integral,oldA=anglePid.integral;
        const float deadbandUnits=HEIGHT_DEADBAND_MM*HEIGHT_SCALE;
        float heightErr=target-height;
        if (fabsf(heightErr)<=deadbandUnits) heightErr=0.0f;
        else heightErr-=copysignf(deadbandUnits,heightErr);
        const float common=BASE_PERCENT+heightPid.step(heightErr,velocity,dt);
        const float diff=MIX_SIGN*anglePid.step(angleTarget-angle(),angularVelocity,dt);
        const float l=common-diff,r=common+diff;
        gradualOutputs(l,r,CONTROL_RATE,outputDt);
        // Freeze only integral changes that push farther beyond achievable outputs.
        const float residualL = l-left, residualR = r-right;
        if ((heightPid.integral-oldH)*(residualL+residualR)>0) heightPid.integral=oldH;
        if (MIX_SIGN*(anglePid.integral-oldA)*(residualR-residualL)>0) anglePid.integral=oldA;
    }else{writeOutputs(0,0);heightPid.integral=anglePid.integral=0;}
    Serial.printf("CTRL,%lu,%u,%u,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%u,%s,%s,%.2f\n",
        (unsigned long)now,armed,originReady,height,target,angle(),angleTarget,left,right,fresh(),
        !armed ? "IDLE" : mode == Mode::Auto ? "AUTO" : "MANUAL", powerName(), rawAngle());
}
}
