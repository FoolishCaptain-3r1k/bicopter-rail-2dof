#pragma once

#include <cstdint>

#ifndef VL53_EMA_ALPHA
#define VL53_EMA_ALPHA 0.4f
#endif

static_assert(VL53_EMA_ALPHA > 0.0f && VL53_EMA_ALPHA <= 1.0f,
              "VL53_EMA_ALPHA must be in (0, 1]");

class MedianEmaFilter {
public:
    struct Result {
        bool ready;
        uint16_t median_mm;
        float filtered_mm;
    };

    void reset() {
        count_ = 0;
        next_ = 0;
        ema_ready_ = false;
        ema_mm_ = 0.0f;
    }

    Result pushValid(uint16_t raw_mm) {
        window_[next_] = raw_mm;
        next_ = (next_ + 1U) % 3U;
        if (count_ < 3U) {
            ++count_;
        }
        if (count_ < 3U) {
            return {false, 0, 0.0f};
        }

        uint16_t a = window_[0];
        uint16_t b = window_[1];
        uint16_t c = window_[2];
        if (a > b) swap(a, b);
        if (b > c) swap(b, c);
        if (a > b) swap(a, b);
        const uint16_t median_mm = b;

        if (!ema_ready_) {
            ema_mm_ = static_cast<float>(median_mm);
            ema_ready_ = true;
        } else {
            ema_mm_ += VL53_EMA_ALPHA * (static_cast<float>(median_mm) - ema_mm_);
        }
        return {true, median_mm, ema_mm_};
    }

private:
    static void swap(uint16_t& a, uint16_t& b) {
        const uint16_t temp = a;
        a = b;
        b = temp;
    }

    uint16_t window_[3] = {0, 0, 0};
    uint8_t count_ = 0;
    uint8_t next_ = 0;
    bool ema_ready_ = false;
    float ema_mm_ = 0.0f;
};
