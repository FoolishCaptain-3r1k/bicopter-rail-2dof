#include "kalman_1d.h"

#include <cmath>

namespace bicopter {

Kalman1D::Kalman1D(float q_pos, float q_vel, float r_meas)
    : q_pos_(q_pos > 0.0f ? q_pos : 1e-6f),
      q_vel_(q_vel > 0.0f ? q_vel : 1e-6f),
      r_meas_(r_meas > 0.0f ? r_meas : 1e-6f) {
    reset(0.0f, 0.0f);
}

void Kalman1D::reset(float x0, float v0) {
    x_[0] = std::isfinite(x0) ? x0 : 0.0f;
    x_[1] = std::isfinite(v0) ? v0 : 0.0f;
    p_[0][0] = 1.0f;
    p_[0][1] = 0.0f;
    p_[1][0] = 0.0f;
    p_[1][1] = 1.0f;
}

void Kalman1D::set_noise(float q_pos, float q_vel, float r_meas) {
    if (q_pos > 0.0f && std::isfinite(q_pos)) {
        q_pos_ = q_pos;
    }
    if (q_vel > 0.0f && std::isfinite(q_vel)) {
        q_vel_ = q_vel;
    }
    if (r_meas > 0.0f && std::isfinite(r_meas)) {
        r_meas_ = r_meas;
    }
}

void Kalman1D::predict(float accel_input, float dt_s) {
    if (!(dt_s > 0.0f) || !std::isfinite(dt_s) || !std::isfinite(accel_input)) {
        return;
    }

    // State extrapolation: x_k = F * x_{k-1} + B * u
    x_[0] += x_[1] * dt_s + 0.5f * accel_input * dt_s * dt_s;
    x_[1] += accel_input * dt_s;

    // Covariance extrapolation: P = F * P * F^T + Q * dt
    const float p00 = p_[0][0];
    const float p01 = p_[0][1];
    const float p10 = p_[1][0];
    const float p11 = p_[1][1];

    const float new_p00 = p00 + dt_s * (p10 + p01) + dt_s * dt_s * p11 + q_pos_ * dt_s;
    const float new_p01 = p01 + dt_s * p11;
    const float new_p10 = p10 + dt_s * p11;
    const float new_p11 = p11 + q_vel_ * dt_s;

    const float sym_off = 0.5f * (new_p01 + new_p10);
    p_[0][0] = new_p00 > 1e-9f ? new_p00 : 1e-9f;
    p_[0][1] = sym_off;
    p_[1][0] = sym_off;
    p_[1][1] = new_p11 > 1e-9f ? new_p11 : 1e-9f;
}

KalmanState Kalman1D::update(float measurement) {
    if (!std::isfinite(measurement)) {
        return KalmanState{x_[0], x_[1], 0.0f};
    }

    const float innovation = measurement - x_[0];
    const float s = p_[0][0] + r_meas_;
    const float k0 = p_[0][0] / s;
    const float k1 = p_[1][0] / s;

    x_[0] += k0 * innovation;
    x_[1] += k1 * innovation;

    const float p00 = p_[0][0];
    const float p01 = p_[0][1];
    const float p10 = p_[1][0];
    const float p11 = p_[1][1];

    const float new_p00 = (1.0f - k0) * p00;
    const float new_p01 = (1.0f - k0) * p01;
    const float new_p10 = p10 - k1 * p00;
    const float new_p11 = p11 - k1 * p01;

    const float sym_off = 0.5f * (new_p01 + new_p10);
    p_[0][0] = new_p00 > 1e-9f ? new_p00 : 1e-9f;
    p_[0][1] = sym_off;
    p_[1][0] = sym_off;
    p_[1][1] = new_p11 > 1e-9f ? new_p11 : 1e-9f;

    return KalmanState{x_[0], x_[1], innovation};
}

}  // namespace bicopter
