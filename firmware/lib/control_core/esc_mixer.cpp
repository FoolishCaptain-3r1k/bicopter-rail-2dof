#include "esc_mixer.h"

#include <cmath>

namespace bicopter {

EscMixer::EscMixer(uint16_t max_throttle_us, bool limits_enabled)
    : state_(ArmState::DISARMED),
      max_throttle_us_(max_throttle_us >= PWM_MIN_US ? max_throttle_us : PWM_MIN_US),
      limits_enabled_(limits_enabled) {}

void EscMixer::set_state(ArmState state) {
    state_ = state;
}

void EscMixer::set_max_throttle_us(uint16_t max_throttle_us) {
    max_throttle_us_ = max_throttle_us >= PWM_MIN_US ? max_throttle_us : PWM_MIN_US;
}

EscCommand EscMixer::mix(float u_base_thrust, float u_torque, float angle_deg, float pos_cm) {
    // 1. Envelope safety cutoff latches ESTOP when limits are active
    if (limits_enabled_) {
        const bool bad_angle = !std::isfinite(angle_deg) || (std::fabs(angle_deg) > DEFAULT_ANGLE_LIMIT_DEG);
        const bool bad_pos = !std::isfinite(pos_cm) || (pos_cm < DEFAULT_POS_MIN_CM) || (pos_cm > DEFAULT_POS_MAX_CM);
        if (bad_angle || bad_pos) {
            state_ = ArmState::ESTOP;
            return EscCommand{PWM_MIN_US, PWM_MIN_US, false, true};
        }
    }

    // 2. Non-ARMED states strictly emit PWM_MIN_US (1000 us)
    if (state_ != ArmState::ARMED) {
        return EscCommand{PWM_MIN_US, PWM_MIN_US, false, state_ == ArmState::ESTOP};
    }

    if (!std::isfinite(u_base_thrust) || !std::isfinite(u_torque)) {
        state_ = ArmState::ESTOP;
        return EscCommand{PWM_MIN_US, PWM_MIN_US, false, true};
    }

    const float raw_left = static_cast<float>(PWM_MIN_US) + u_base_thrust + u_torque;
    const float raw_right = static_cast<float>(PWM_MIN_US) + u_base_thrust - u_torque;

    const float min_f = static_cast<float>(PWM_MIN_US);
    const float max_f = static_cast<float>(max_throttle_us_);

    bool clamped = false;
    float left_f = raw_left;
    float right_f = raw_right;

    if (left_f < min_f) {
        left_f = min_f;
        clamped = true;
    } else if (left_f > max_f) {
        left_f = max_f;
        clamped = true;
    }

    if (right_f < min_f) {
        right_f = min_f;
        clamped = true;
    } else if (right_f > max_f) {
        right_f = max_f;
        clamped = true;
    }

    return EscCommand{
        static_cast<uint16_t>(std::lround(left_f)),
        static_cast<uint16_t>(std::lround(right_f)),
        clamped,
        false
    };
}

}  // namespace bicopter
