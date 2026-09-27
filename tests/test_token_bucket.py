import math
from fractions import Fraction

import pytest

from codey_estimator.errors import PricingPolicyError
from codey_estimator.refresh import TokenBucket


def test_tb1_sequence(fake_clock):
    fake_clock.t = 0
    bucket = TokenBucket.per_minute(3, fake_clock)

    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False
    assert bucket.seconds_until_available() == Fraction(20)

    fake_clock.t = 10
    assert bucket.available() == Fraction(1, 2)
    assert bucket.try_acquire() is False
    assert bucket.seconds_until_available() == Fraction(10)

    fake_clock.t = 20
    assert bucket.try_acquire() is True

    fake_clock.t = 1020
    assert bucket.available() == Fraction(3)
    assert bucket.try_acquire(3) is True

    with pytest.raises(PricingPolicyError) as excinfo:
        bucket.try_acquire(4)
    assert excinfo.value.code == "TOKENS_EXCEED_CAPACITY"

    with pytest.raises(PricingPolicyError) as excinfo:
        bucket.try_acquire(0)
    assert excinfo.value.code == "TOKENS_INVALID"


def test_tb2_fractional_and_backwards_clock(fake_clock):
    fake_clock.t = 0.0
    bucket = TokenBucket.per_minute(60, fake_clock)

    for _ in range(60):
        assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False

    fake_clock.t = 0.25
    assert bucket.available() == Fraction(1, 4)

    fake_clock.t = 0.75
    assert bucket.available() == Fraction(3, 4)

    fake_clock.t = 1.0
    assert bucket.try_acquire() is True

    fake_clock.t = 0.5
    assert bucket.available() == Fraction(0)

    fake_clock.t = 1.5
    assert bucket.available() == Fraction(1, 2)


def test_tb3_seconds_until_multi(fake_clock):
    fake_clock.t = 0
    bucket = TokenBucket(3, 1, 60, fake_clock)
    assert bucket.try_acquire(3) is True
    assert bucket.seconds_until_available(2) == Fraction(120)


def test_bucket_config_validation(fake_clock):
    fake_clock.t = 0
    with pytest.raises(PricingPolicyError) as excinfo:
        TokenBucket(0, 1, 60, fake_clock)
    assert excinfo.value.code == "BUCKET_CONFIG_INVALID"

    with pytest.raises(PricingPolicyError):
        TokenBucket(3, 0, 60, fake_clock)

    with pytest.raises(PricingPolicyError):
        TokenBucket(3, 1, 0, fake_clock)

    with pytest.raises(TypeError):
        TokenBucket(True, 1, 60, fake_clock)


def test_clock_nan_rejected(fake_clock):
    fake_clock.t = math.nan
    with pytest.raises(PricingPolicyError) as excinfo:
        TokenBucket(3, 1, 60, fake_clock)
    assert excinfo.value.code == "CLOCK_NOT_FINITE"


def test_clock_bool_rejected():
    def bad_clock():
        return True

    with pytest.raises(TypeError):
        TokenBucket(3, 1, 60, bad_clock)
