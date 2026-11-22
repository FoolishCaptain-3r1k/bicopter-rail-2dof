#pragma once

#include <cstdint>

namespace bicopter {

enum class DampingMode : uint8_t {
    UNDERDAMPED,
    CRITICALLY_DAMPED,
    OVERDAMPED
};

struct PlantParams {
    float wn_rad_s;
    float gain_k;
    float damping_b;
};

struct PidGains {
    float kp;
    float ki;
    float kd;
    float d_filter_tau;
};

struct PidOutput {
    float u;
    float error;
    float p_term;
    float i_term;
    float d_term;
};

/**
 * @brief Synthesize closed-loop PID gains for a 2nd-order plant (y'' + b*y' = K*u)
 *        targeting zeta ~= 0.45 (UNDERDAMPED), 1.0 (CRITICALLY_DAMPED), or 1.6 (OVERDAMPED).
 */
PidGains synthesize_pid_gains(DampingMode mode, const PlantParams& plant);

/**
 * @brief Hardware-independent PID controller with filtered derivative-on-measurement and clamping anti-windup.
 */
class PidController {
public:
    PidController();
    explicit PidController(const PidGains& gains);

    void set_gains(const PidGains& gains);
    PidGains gains() const { return gains_; }
    void reset();

    PidOutput step(float setpoint, float measurement, float dt_s, float u_min, float u_max);

private:
    PidGains gains_;
    float integral_;
    float d_meas_filt_;
    float prev_measurement_;
    bool has_prev_;
};

}  // namespace bicopter
