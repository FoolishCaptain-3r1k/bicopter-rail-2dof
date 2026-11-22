#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <random>

#include "esc_mixer.h"
#include "kalman_1d.h"
#include "pid_controller.h"

namespace {

int g_failures = 0;

void check(bool cond, const char* msg) {
    if (!cond) {
        std::fprintf(stderr, "FAIL: %s\n", msg);
        ++g_failures;
    }
}

struct StepMetrics {
    float max_y;
    float final_y;
    float overshoot_pct;
    float settling_time_s;
};

StepMetrics simulate_step_response(bicopter::DampingMode mode, const bicopter::PlantParams& plant) {
    const bicopter::PidGains gains = bicopter::synthesize_pid_gains(mode, plant);
    bicopter::PidController pid(gains);
    pid.reset();

    const float dt = 0.002f;
    const int steps = 2500;  // 5.0 s
    const float setpoint = 1.0f;

    float y = 0.0f;
    float v = 0.0f;
    float max_y = 0.0f;
    float last_outside_band_s = 0.0f;

    for (int i = 0; i < steps; ++i) {
        const float t = static_cast<float>(i) * dt;
        const bicopter::PidOutput out = pid.step(setpoint, y, dt, -100.0f, 100.0f);

        // 2nd-order plant: y'' + b * y' = K * u (semi-implicit Euler)
        const float accel = plant.gain_k * out.u - plant.damping_b * v;
        v += accel * dt;
        y += v * dt;

        if (y > max_y) {
            max_y = y;
        }
        if (std::fabs(y - setpoint) > 0.02f * setpoint) {
            last_outside_band_s = t;
        }
    }

    const float overshoot_pct = (max_y > setpoint) ? ((max_y - setpoint) / setpoint) * 100.0f : 0.0f;
    return StepMetrics{max_y, y, overshoot_pct, last_outside_band_s};
}

void test_kalman_noise_variance_reduction() {
    bicopter::Kalman1D kf(1e-3f, 2e-1f, 2.25f);
    kf.reset(0.0f, 0.0f);

    std::mt19937 rng(42);
    std::normal_distribution<float> noise(0.0f, 1.5f);

    const float dt = 0.01f;
    const int steps = 600;
    double sum_sq_raw = 0.0;
    double sum_sq_est = 0.0;
    double sum_sq_vel = 0.0;

    for (int i = 0; i < steps; ++i) {
        const float t = static_cast<float>(i) * dt;
        const float true_pos = 10.0f * (1.0f - std::cos(1.2f * t));
        const float true_vel = 12.0f * std::sin(1.2f * t);
        const float true_acc = 14.4f * std::cos(1.2f * t);
        const float meas = true_pos + noise(rng);

        kf.predict(true_acc, dt);
        const bicopter::KalmanState st = kf.update(meas);

        if (i >= 50) {  // Ignore brief initial convergence
            const double raw_err = static_cast<double>(meas - true_pos);
            const double est_err = static_cast<double>(st.pos - true_pos);
            const double vel_err = static_cast<double>(st.vel - true_vel);
            sum_sq_raw += raw_err * raw_err;
            sum_sq_est += est_err * est_err;
            sum_sq_vel += vel_err * vel_err;
        }
    }

    const double n = static_cast<double>(steps - 50);
    const double var_raw = sum_sq_raw / n;
    const double var_est = sum_sq_est / n;
    const double rms_vel = std::sqrt(sum_sq_vel / n);

    std::printf("[KALMAN] var_raw=%.3f var_est=%.3f reduction=%.1f%% rms_vel=%.3f\n",
                var_raw, var_est, (1.0 - var_est / var_raw) * 100.0, rms_vel);
    check(var_est < 0.35 * var_raw, "Kalman1D must reduce measurement error variance by > 65%");
    check(rms_vel < 1.0, "Kalman1D velocity estimate must track true velocity");
}

void test_pid_damping_modes_step_response() {
    const bicopter::PlantParams plant{6.0f, 10.0f, 1.0f};

    const StepMetrics under = simulate_step_response(bicopter::DampingMode::UNDERDAMPED, plant);
    const StepMetrics crit = simulate_step_response(bicopter::DampingMode::CRITICALLY_DAMPED, plant);
    const StepMetrics over = simulate_step_response(bicopter::DampingMode::OVERDAMPED, plant);

    std::printf("[PID] UNDER: os=%.2f%% ts=%.3fs | CRIT: os=%.2f%% ts=%.3fs | OVER: os=%.2f%% ts=%.3fs\n",
                under.overshoot_pct, under.settling_time_s,
                crit.overshoot_pct, crit.settling_time_s,
                over.overshoot_pct, over.settling_time_s);

    check(under.overshoot_pct > 10.0f, "UNDERDAMPED overshoot must exceed 10%");
    check(crit.overshoot_pct <= 2.0f, "CRITICALLY_DAMPED overshoot must be <= 2%");
    check(over.overshoot_pct <= 0.01f, "OVERDAMPED overshoot must be 0%");
    check(over.settling_time_s > crit.settling_time_s, "OVERDAMPED must settle slower than CRITICALLY_DAMPED");
    check(std::fabs(under.final_y - 1.0f) < 0.02f, "UNDERDAMPED must converge to setpoint");
    check(std::fabs(crit.final_y - 1.0f) < 0.02f, "CRITICALLY_DAMPED must converge to setpoint");
    check(std::fabs(over.final_y - 1.0f) < 0.02f, "OVERDAMPED must converge to setpoint");
}

void test_pid_anti_windup_and_deterministic_reset() {
    bicopter::PidController pid(bicopter::PidGains{2.0f, 8.0f, 0.2f, 0.02f});
    pid.reset();

    // Saturate positive for 2.0 s under large constant error
    bicopter::PidOutput last{};
    for (int i = 0; i < 200; ++i) {
        last = pid.step(50.0f, 0.0f, 0.01f, -10.0f, 10.0f);
    }
    check(last.u <= 10.0f + 1e-5f, "PID output must respect upper clamp");
    check(last.i_term <= 10.0f + 1e-5f, "Anti-windup must clamp integral term");

    // Step immediately below measurement: without windup, output drops promptly
    const bicopter::PidOutput drop = pid.step(-20.0f, 0.0f, 0.01f, -10.0f, 10.0f);
    check(drop.u < 0.0f, "Anti-windup must allow immediate control reversal");

    // Deterministic reset verification
    pid.reset();
    const bicopter::PidOutput run1_a = pid.step(5.0f, 1.0f, 0.01f, -10.0f, 10.0f);
    const bicopter::PidOutput run1_b = pid.step(5.0f, 1.5f, 0.01f, -10.0f, 10.0f);

    pid.reset();
    const bicopter::PidOutput run2_a = pid.step(5.0f, 1.0f, 0.01f, -10.0f, 10.0f);
    const bicopter::PidOutput run2_b = pid.step(5.0f, 1.5f, 0.01f, -10.0f, 10.0f);

    check(run1_a.u == run2_a.u && run1_a.i_term == run2_a.i_term && run1_a.d_term == run2_a.d_term,
          "reset() must produce bit-identical first step");
    check(run1_b.u == run2_b.u && run1_b.i_term == run2_b.i_term && run1_b.d_term == run2_b.d_term,
          "reset() must produce bit-identical second step");
}

void test_esc_mixer_safety_and_throttle_cap() {
    bicopter::EscMixer mixer(1450, true);

    // DISARMED strictly outputs 1000 us
    const bicopter::EscCommand dis = mixer.mix(300.0f, 50.0f, 0.0f, 10.0f);
    check(dis.pwm_left_us == 1000 && dis.pwm_right_us == 1000 && !dis.fault,
          "DISARMED must emit 1000 us");

    // ARMING strictly outputs 1000 us
    mixer.set_state(bicopter::ArmState::ARMING);
    const bicopter::EscCommand arming = mixer.mix(300.0f, 50.0f, 0.0f, 10.0f);
    check(arming.pwm_left_us == 1000 && arming.pwm_right_us == 1000 && !arming.fault,
          "ARMING must emit 1000 us");

    // ARMED nominal mixing
    mixer.set_state(bicopter::ArmState::ARMED);
    const bicopter::EscCommand nom = mixer.mix(200.0f, 40.0f, 5.0f, 12.0f);
    check(nom.pwm_left_us == 1240 && nom.pwm_right_us == 1160 && !nom.clamped && !nom.fault,
          "ARMED nominal mixing must compute 1000 + thrust +/- torque");

    // Hard throttle cap at 1450 us
    const bicopter::EscCommand capped = mixer.mix(420.0f, 100.0f, 5.0f, 12.0f);
    check(capped.pwm_left_us == 1450 && capped.pwm_right_us == 1320 && capped.clamped && !capped.fault,
          "Hard throttle cap must clamp ESC output at MAX_THROTTLE_US=1450");

    // Angle cutoff (> 60 deg) latches ESTOP at 1000 us
    const bicopter::EscCommand ang_fault = mixer.mix(200.0f, 0.0f, 61.0f, 12.0f);
    check(ang_fault.pwm_left_us == 1000 && ang_fault.pwm_right_us == 1000 && ang_fault.fault,
          "|angle| > 60 deg must force 1000 us and fault");
    check(mixer.state() == bicopter::ArmState::ESTOP, "|angle| > 60 deg must latch ESTOP");

    // Remains latched in ESTOP even after angle returns safe
    const bicopter::EscCommand latched = mixer.mix(200.0f, 0.0f, 0.0f, 12.0f);
    check(latched.pwm_left_us == 1000 && latched.pwm_right_us == 1000 && latched.fault,
          "ESTOP must remain latched until explicitly cleared");

    // Rail position out-of-bounds (< 0 or > 23 cm) latches ESTOP
    mixer.set_state(bicopter::ArmState::ARMED);
    const bicopter::EscCommand pos_fault = mixer.mix(200.0f, 0.0f, 0.0f, 23.5f);
    check(pos_fault.pwm_left_us == 1000 && pos_fault.pwm_right_us == 1000 && pos_fault.fault,
          "Position > 23 cm must force 1000 us and latch ESTOP");
    check(mixer.state() == bicopter::ArmState::ESTOP, "Position fault must latch ESTOP");
}

}  // namespace

int main() {
    test_kalman_noise_variance_reduction();
    test_pid_damping_modes_step_response();
    test_pid_anti_windup_and_deterministic_reset();
    test_esc_mixer_safety_and_throttle_cap();

    if (g_failures == 0) {
        std::printf("PASS: all control_core native unit tests passed (0 failed)\n");
        return 0;
    }
    std::fprintf(stderr, "TOTAL FAILURES: %d\n", g_failures);
    return 1;
}
