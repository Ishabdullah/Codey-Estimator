import pytest

from codey_estimator.errors import PricingPolicyError
from codey_estimator.refresh import CircuitBreaker, CircuitState, backoff_seconds


@pytest.mark.parametrize(
    "attempt,expected",
    [
        (1, 60),
        (2, 120),
        (3, 240),
        (5, 960),
        (10, 30_720),
        (11, 61_440),
        (12, 86_400),
        (50, 86_400),
        (10**6, 86_400),
    ],
)
def test_backoff_default_schedule(attempt, expected):
    assert backoff_seconds(attempt) == expected


def test_backoff_custom_schedule():
    expected = [30, 90, 270, 810, 1_000]
    for attempt, exp in enumerate(expected, start=1):
        assert backoff_seconds(attempt, base_seconds=30, factor=3, max_seconds=1_000) == exp


def test_backoff_factor_one():
    assert backoff_seconds(7, base_seconds=45, factor=1) == 45


def test_backoff_large_attempt_is_fast():
    import time

    start = time.monotonic()
    result = backoff_seconds(10**6)
    elapsed = time.monotonic() - start
    assert result == 86_400
    assert elapsed < 1.0


def test_backoff_validation():
    with pytest.raises(PricingPolicyError) as excinfo:
        backoff_seconds(0)
    assert excinfo.value.code == "BACKOFF_ATTEMPT_INVALID"

    with pytest.raises(PricingPolicyError) as excinfo:
        backoff_seconds(1, base_seconds=0)
    assert excinfo.value.code == "BACKOFF_CONFIG_INVALID"

    with pytest.raises(PricingPolicyError) as excinfo:
        backoff_seconds(1, base_seconds=60, max_seconds=30)
    assert excinfo.value.code == "BACKOFF_CONFIG_INVALID"


def test_cb1_open_halfopen_closed(fake_clock):
    fake_clock.t = 1000
    cb = CircuitBreaker(3, 300, fake_clock)

    assert cb.allow_request() is True
    cb.record_failure()
    cb.record_failure()
    assert cb.consecutive_failures == 2
    cb.record_success()
    assert cb.consecutive_failures == 0

    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.consecutive_failures == 3
    assert cb.allow_request() is False

    fake_clock.t = 1299
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    fake_clock.t = 1300
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True
    assert cb.allow_request() is False

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0
    assert cb.allow_request() is True


def test_cb2_halfopen_failure_reopens(fake_clock):
    fake_clock.t = 1000
    cb = CircuitBreaker(3, 300, fake_clock)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    fake_clock.t = 1300
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.consecutive_failures == 4
    assert cb.allow_request() is False

    fake_clock.t = 1599
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    fake_clock.t = 1600
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_cb3_results_while_open(fake_clock):
    fake_clock.t = 1000
    cb = CircuitBreaker(3, 300, fake_clock)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    fake_clock.t = 1100
    cb.record_success()
    assert cb.state == CircuitState.OPEN
    assert cb.consecutive_failures == 3

    fake_clock.t = 1200
    cb.record_failure()
    assert cb.consecutive_failures == 4

    fake_clock.t = 1300
    assert cb.state == CircuitState.HALF_OPEN


def test_cb4_threshold_one_and_config_validation(fake_clock):
    fake_clock.t = 1000
    cb = CircuitBreaker(1, 300, fake_clock)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    with pytest.raises(PricingPolicyError) as excinfo:
        CircuitBreaker(0, 300, fake_clock)
    assert excinfo.value.code == "BREAKER_CONFIG_INVALID"

    with pytest.raises(PricingPolicyError) as excinfo:
        CircuitBreaker(1, 0, fake_clock)
    assert excinfo.value.code == "BREAKER_CONFIG_INVALID"


def test_cb5_state_read_is_pure(fake_clock):
    fake_clock.t = 1000
    cb = CircuitBreaker(3, 300, fake_clock)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()

    fake_clock.t = 1300
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True
