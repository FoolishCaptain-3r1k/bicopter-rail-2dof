#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>

struct ImuSample {
    uint32_t ts_ms = 0;
    float roll = 0, pitch = 0, yaw = 0;
    float gx = 0, gy = 0, gz = 0;
    float ax = 0, ay = 0, az = 0;
    float qw = 1, qx = 0, qy = 0, qz = 0;
    uint8_t cal_sys = 0, cal_gyro = 0, cal_accel = 0, cal_mag = 0;
    float hz = 0;
    uint32_t seq = 0;
    bool valid = false;
};

inline void mapEuler(float heading_x, float roll_y, float pitch_z, ImuSample& s) {
    s.roll = roll_y;
    s.pitch = pitch_z;
    s.yaw = heading_x;
}

inline const char* invalidReason(const ImuSample& s) {
    const float v[] = {s.roll,s.pitch,s.yaw,s.gx,s.gy,s.gz,s.ax,s.ay,s.az,s.qw,s.qx,s.qy,s.qz};
    const char* names[] = {"roll","pitch","yaw","gx","gy","gz","ax","ay","az","qw","qx","qy","qz"};
    for (unsigned i=0;i<sizeof(v)/sizeof(v[0]);++i) if (!std::isfinite(v[i])) return names[i];
    const float norm = s.qw*s.qw+s.qx*s.qx+s.qy*s.qy+s.qz*s.qz;
    if (!std::isfinite(norm) || norm <= 0.5f || norm >= 1.5f) return "quaternion_norm";
    return nullptr;
}
inline bool finiteSample(const ImuSample& s) { return invalidReason(s)==nullptr; }

inline bool fresh(const ImuSample& s, uint32_t now, uint32_t max_age_ms = 200) {
    return s.valid && s.seq != 0 && static_cast<uint32_t>(now - s.ts_ms) <= max_age_ms;
}

inline int csvLine(char* out, size_t n, const ImuSample& s, bool current) {
    if (!current) return std::snprintf(out,n,"%lu,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,INVALID\n",static_cast<unsigned long>(s.ts_ms));
    return std::snprintf(out,n,"%lu,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%u,%u,%u,%u,OK\n",
        static_cast<unsigned long>(s.ts_ms),s.roll,s.pitch,s.yaw,s.gx,s.gy,s.gz,s.ax,s.ay,s.az,
        s.cal_sys,s.cal_gyro,s.cal_accel,s.cal_mag);
}

inline int jsonLine(char* out, size_t n, const ImuSample& s, uint32_t now, bool connected, const char* mode, uint8_t address, uint32_t errors) {
    const uint32_t age = s.seq ? static_cast<uint32_t>(now-s.ts_ms) : 0;
    const bool ok = connected && fresh(s,now);
    const char* status = !connected ? "DISCONNECTED" : (ok ? "OK" : "STALE_OR_INVALID");
    const int head = std::snprintf(out,n,"{\"status\":\"%s\",\"valid\":%s,\"ts_ms\":%lu,\"age_ms\":%lu,\"mode\":\"%s\",\"i2c\":\"0x%02X\",\"hz\":%.1f,\"errors\":%lu,\"data\":",
        status,ok?"true":"false",static_cast<unsigned long>(s.ts_ms),static_cast<unsigned long>(age),mode,address,s.hz,static_cast<unsigned long>(errors));
    if (head < 0 || static_cast<size_t>(head) >= n) return -1;
    const int tail = ok ? std::snprintf(out+head,n-head,"{\"roll\":%.2f,\"pitch\":%.2f,\"yaw\":%.2f,\"gx\":%.2f,\"gy\":%.2f,\"gz\":%.2f,\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"qw\":%.4f,\"qx\":%.4f,\"qy\":%.4f,\"qz\":%.4f,\"cal\":[%u,%u,%u,%u]}}",
        s.roll,s.pitch,s.yaw,s.gx,s.gy,s.gz,s.ax,s.ay,s.az,s.qw,s.qx,s.qy,s.qz,s.cal_sys,s.cal_gyro,s.cal_accel,s.cal_mag)
        : std::snprintf(out+head,n-head,"null}");
    return tail < 0 || static_cast<size_t>(tail) >= n-head ? -1 : head+tail;
}
