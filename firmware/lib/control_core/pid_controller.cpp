#include "pid_controller.h"

#include <cmath>

namespace bicopter {

namespace {

float clamp_float(float val, float lo, float hi) {
    if (val < lo) {
        return lo;
    }
    if (val > hi) {
        return hi;
    }
    return val;
}

}  // namespace

PidGains synthesize_pid_gains(DampingMode mode, const PlantParams& plant) {
    const float wn = (plant.wn_rad_s > 0.0f && std::isfinite(plant.wn_rad_s)) ? plant.wn_rad_s : 1.0f;
    const float k = (plant.gain_k > 1e-6f && std::isfinite(plant.gain_k)) ? plant.gain_k : 1.0f;
    const float b = std::isfinite(plant.damping_b) ? plant.damping_b : 0.0f;

    float zeta = 1.0f;
    float ki_ratio = 0.0f;
    switch (mode) {
        case DampingMode::UNDERDAMPED:
            zeta = 0.45f;
            ki_ratio = 0.05f;
            break;
        case DampingMode::CRITICALLY_DAMPED:
            zeta = 1.0f;
            ki_ratio = 0.01f;
            break;
        case DampingMode::OVERDAMPED:
            zeta = 1.6f;
            ki_ratio = 0.0f;
            break;
    }

    const float kp = (wn * wn) / k;
    const float kd_raw = (2.0f * zeta * wn - b) / k;
    const float kd = kd_raw > 0.0f ? kd_raw : 0.0f;
    const float ki = ki_ratio * kp;
    const float d_tau = 1.0f / (12.0f * wn);

    return PidGains{kp, ki, kd, d_tau};
}

PidController::PidController()
    : gains_{0.0f, 0.0f, 0.0f, 0.02f},
      integral_(0.0f),
      d_meas_filt_(0.0f),
      prev_measurement_(0.0f),
      has_prev_(false) {}

PidController::PidController(const PidGains& gains)
    : gains_(gains),
      integral_(0.0f),
      d_meas_filt_(0.0f),
      prev_measurement_(0.0f),
      has_prev_(false) {}

void PidController::set_gains(const PidGains& gains) {
    gains_ = gains;
}

void PidController::reset() {
    integral_ = 0.0f;
    d_meas_filt_ = 0.0f;
    prev_measurement_ = 0.0f;
    has_prev_ = false;
}

PidOutput PidController::step(float setpoint, float measurement, float dt_s, float u_min, float u_max) {
    if (u_min > u_max) {
        const float tmp = u_min;
        u_min = u_max;
        u_max = tmp;
    }

    if (!(dt_s > 0.0f) || !std::isfinite(dt_s) || !std::isfinite(setpoint) || !std::isfinite(measurement)) {
        const float safe_u = clamp_float(0.0f, u_min, u_max);
        return PidOutput{safe_u, 0.0f, 0.0f, integral_, 0.0f};
    }

    const float error = setpoint - measurement;
    const float p_term = gains_.kp * error;

    // Derivative on measurement with 1st-order low-pass filter (avoids setpoint derivative kick)
    if (!has_prev_) {
        prev_measurement_ = measurement;
        d_meas_filt_ = 0.0f;
        has_prev_ = true;
    } else {
        const float raw_d_meas = (measurement - prev_measurement_) / dt_s;
        const float tau = gains_.d_filter_tau > 0.0f ? gains_.d_filter_tau : 0.0f;
        const float alpha = dt_s / (tau + dt_s);
        d_meas_filt_ += alpha * (raw_d_meas - d_meas_filt_);
        prev_measurement_ = measurement;
    }
    const float d_term = -gains_.kd * d_meas_filt_;

    // Conditional-integration clamping anti-windup
    const float i_candidate = clamp_float(integral_ + gains_.ki * error * dt_s, u_min, u_max);
    const float u_unsat = p_term + i_candidate + d_term;
    const bool pushing_high = (u_unsat > u_max) && (error > 0.0f);
    const bool pushing_low = (u_unsat < u_min) && (error < 0.0f);

    if (!pushing_high && !pushing_low) {
        integral_ = i_candidate;
    }

    const float u_final = clamp_float(p_term + integral_ + d_term, u_min, u_max);
    return PidOutput{u_final, error, p_term, integral_, d_term};
}

}  // namespace bicopter
