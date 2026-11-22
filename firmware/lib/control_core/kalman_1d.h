#pragma once

namespace bicopter {

struct KalmanState {
    float pos;
    float vel;
    float innovation;
};

/**
 * @brief Hardware-independent 2-state 1D Kalman filter ([pos, vel]).
 *
 * Suitable for estimating either tilt angle (theta, theta_dot) or rail position (x, x_dot).
 */
class Kalman1D {
public:
    explicit Kalman1D(float q_pos = 1e-3f, float q_vel = 1e-2f, float r_meas = 1.0f);

    void reset(float x0 = 0.0f, float v0 = 0.0f);
    void set_noise(float q_pos, float q_vel, float r_meas);

    void predict(float accel_input, float dt_s);
    KalmanState update(float measurement);

    float pos() const { return x_[0]; }
    float vel() const { return x_[1]; }
    float p00() const { return p_[0][0]; }
    float p11() const { return p_[1][1]; }

private:
    float x_[2];
    float p_[2][2];
    float q_pos_;
    float q_vel_;
    float r_meas_;
};

}  // namespace bicopter
