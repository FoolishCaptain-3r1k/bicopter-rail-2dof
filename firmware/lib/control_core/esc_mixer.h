#pragma once

#include <cstdint>

namespace bicopter {

enum class ArmState : uint8_t {
    DISARMED,
    ARMING,
    ARMED,
    ESTOP
};

struct EscCommand {
    uint16_t pwm_left_us;
    uint16_t pwm_right_us;
    bool clamped;
    bool fault;
};

/**
 * @brief Safety-first dual-ESC thrust/torque mixer with hard throttle cap and envelope ESTOP.
 *
 * Invariants:
 * - Strictly outputs 1000 us whenever state != ARMED.
 * - Hard-clamps both ESCs to [1000, max_throttle_us] (default 1450 us for 2S LiPo + KV11000).
 * - Automatically latches ESTOP if limits are enabled and |angle_deg| > 60 deg or pos_cm not in [0, 23] cm.
 */
class EscMixer {
public:
    static constexpr uint16_t PWM_MIN_US = 1000;
    static constexpr uint16_t DEFAULT_MAX_THROTTLE_US = 1450;
    static constexpr float DEFAULT_ANGLE_LIMIT_DEG = 60.0f;
    static constexpr float DEFAULT_POS_MIN_CM = 0.0f;
    static constexpr float DEFAULT_POS_MAX_CM = 23.0f;

    explicit EscMixer(
        uint16_t max_throttle_us = DEFAULT_MAX_THROTTLE_US,
        bool limits_enabled = true);

    void set_state(ArmState state);
    ArmState state() const { return state_; }

    void set_max_throttle_us(uint16_t max_throttle_us);
    uint16_t max_throttle_us() const { return max_throttle_us_; }

    void set_limits_enabled(bool enabled) { limits_enabled_ = enabled; }
    bool limits_enabled() const { return limits_enabled_; }

    /**
     * @brief Mix base thrust delta (us above 1000) and differential torque delta (us).
     */
    EscCommand mix(float u_base_thrust, float u_torque, float angle_deg, float pos_cm);

private:
    ArmState state_;
    uint16_t max_throttle_us_;
    bool limits_enabled_;
};

}  // namespace bicopter
