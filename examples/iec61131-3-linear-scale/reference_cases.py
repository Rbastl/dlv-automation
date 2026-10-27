#!/usr/bin/env python3
"""Reference maths for the vendor-neutral ST illustration. Does not compile ST."""
from math import isclose


def scale(raw, raw_low, raw_high, eu_low, eu_high, enable=True):
    if not enable:
        return 0.0, 0.0, False, 1
    if abs(raw_high - raw_low) < 1e-9:
        return 0.0, 0.0, False, 2
    fraction = (raw - raw_low) / (raw_high - raw_low)
    eu = eu_low + fraction * (eu_high - eu_low)
    if fraction < 0:
        return eu, fraction, False, 3
    if fraction > 1:
        return eu, fraction, False, 4
    return eu, fraction, True, 0


def check(raw, low, high, exp_value, exp_valid, exp_status):
    eu, frac, valid, status = scale(raw, low, high, 0, 10)
    assert isclose(eu, exp_value), (raw, eu, exp_value)
    assert valid is exp_valid, (raw, valid, exp_valid)
    assert status == exp_status, (raw, status, exp_status)


if __name__ == "__main__":
    check(100, 100, 200, 0.0, True, 0)
    check(150, 100, 200, 5.0, True, 0)
    check(200, 100, 200, 10.0, True, 0)
    check(90, 100, 200, -1.0, False, 3)
    check(220, 100, 200, 12.0, False, 4)
    check(150, 200, 100, 5.0, True, 0)
    assert scale(150, 100, 100, 0, 10)[-1] == 2
    assert scale(150, 100, 200, 0, 10, enable=False)[-1] == 1
    print("PASS: 8 independent analog scaling reference cases")
