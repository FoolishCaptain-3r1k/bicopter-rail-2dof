#include <cmath>
#include <cstdlib>
#include <iostream>

#include "median_ema_filter.h"

void check(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}

void near(float actual, float expected, const char* message) {
    check(std::fabs(actual - expected) < 0.01f, message);
}

void testNoise() {
    MedianEmaFilter filter;
    check(!filter.pushValid(100).ready, "noise: first sample must warm up");
    check(!filter.pushValid(102).ready, "noise: second sample must warm up");
    near(filter.pushValid(98).filtered_mm, 100.0f, "noise: median seeds EMA");
    near(filter.pushValid(101).filtered_mm, 100.4f, "noise: EMA after median 101");
    near(filter.pushValid(99).filtered_mm, 99.84f, "noise: EMA after median 99");
}

void testSpike() {
    MedianEmaFilter filter;
    filter.pushValid(100);
    filter.pushValid(100);
    filter.pushValid(100);
    near(filter.pushValid(1000).filtered_mm, 100.0f, "spike: isolated high peak rejected");
    near(filter.pushValid(100).filtered_mm, 100.0f, "spike: output remains at baseline");
}

void testStep() {
    MedianEmaFilter filter;
    filter.pushValid(100);
    filter.pushValid(100);
    filter.pushValid(100);
    near(filter.pushValid(200).filtered_mm, 100.0f, "step: first changed sample held by median");
    near(filter.pushValid(200).filtered_mm, 140.0f, "step: second changed sample starts EMA");
    near(filter.pushValid(200).filtered_mm, 164.0f, "step: EMA approaches new level");
}

void testSensorFailure() {
    MedianEmaFilter filter;
    filter.pushValid(100);
    filter.pushValid(100);
    check(filter.pushValid(100).ready, "failure: filter initially ready");
    // Firmware calls reset for invalid range, timeout, or lost I2C; no invalid value enters pushValid.
    filter.reset();
    check(!filter.pushValid(200).ready, "failure: no stale output after reset");
    check(!filter.pushValid(200).ready, "failure: two fresh samples still warm up");
    const auto recovered = filter.pushValid(200);
    check(recovered.ready, "failure: three fresh samples recover output");
    near(recovered.filtered_mm, 200.0f, "failure: recovered EMA excludes old samples");
}

int main() {
    testNoise();
    testSpike();
    testStep();
    testSensorFailure();
    std::cout << "PASS: noise, spike, step, sensor failure simulations\n";
}
