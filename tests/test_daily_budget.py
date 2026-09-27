import pytest

from codey_estimator.errors import BudgetExceededError, EstimatorError, PricingPolicyError
from codey_estimator.refresh import BudgetState, DailyBudget

T0 = 1_790_000_000
DAY0 = 20717
DAY1 = 20718
MIDNIGHT = 1_790_035_200


def test_b1_sequence_and_midnight_reset(fake_clock):
    fake_clock.t = T0
    budget = DailyBudget(3, fake_clock)

    assert budget.would_exceed() is False
    assert budget.consume() == 2
    assert budget.consume() == 1
    assert budget.consume() == 0
    assert budget.would_exceed() is True
    assert budget.would_exceed() is True
    assert budget.remaining() == 0

    with pytest.raises(BudgetExceededError) as excinfo:
        budget.consume()
    assert excinfo.value.cap == 3
    assert excinfo.value.used == 3
    assert excinfo.value.requested == 1
    assert excinfo.value.code == "DAILY_BUDGET_EXCEEDED"
    assert budget.snapshot() == BudgetState(DAY0, 3)

    fake_clock.t = MIDNIGHT - 1
    assert budget.would_exceed() is True

    fake_clock.t = MIDNIGHT
    assert budget.remaining() == 3
    assert budget.snapshot() == BudgetState(DAY1, 0)
    assert budget.consume() == 2


def test_would_exceed_and_remaining_do_not_mutate(fake_clock):
    fake_clock.t = T0
    budget = DailyBudget(3, fake_clock)
    budget.consume(3)
    before = budget.snapshot()
    budget.would_exceed()
    budget.would_exceed()
    budget.remaining()
    after = budget.snapshot()
    assert before == after == BudgetState(DAY0, 3)


def test_b2_multi_unit(fake_clock):
    fake_clock.t = T0
    budget = DailyBudget(10, fake_clock)
    assert budget.consume(4) == 6
    assert budget.would_exceed(7) is True
    assert budget.would_exceed(6) is False
    assert budget.consume(6) == 0
    with pytest.raises(PricingPolicyError) as excinfo:
        budget.consume(0)
    assert excinfo.value.code == "AMOUNT_INVALID"


def test_b3_utc_offset(fake_clock):
    fake_clock.t = T0
    budget = DailyBudget(3, fake_clock, utc_offset_seconds=-18_000)
    budget.consume(3)

    fake_clock.t = MIDNIGHT
    assert budget.remaining() == 0

    fake_clock.t = 1_790_053_200
    assert budget.remaining() == 3


def test_b4_restore_state(fake_clock):
    fake_clock.t = T0
    b1 = DailyBudget(3, fake_clock, state=BudgetState(DAY0, 2))
    assert b1.remaining() == 1

    b2 = DailyBudget(3, fake_clock, state=BudgetState(DAY0 - 1, 3))
    assert b2.remaining() == 3

    b3 = DailyBudget(3, fake_clock, state=BudgetState(DAY0, 5))
    assert b3.remaining() == 0
    assert b3.would_exceed() is True

    with pytest.raises(PricingPolicyError) as excinfo:
        DailyBudget(3, fake_clock, state=BudgetState(DAY0, -1))
    assert excinfo.value.code == "BUDGET_STATE_INVALID"


def test_b5_backwards_clock_keeps_count(fake_clock):
    fake_clock.t = MIDNIGHT
    budget = DailyBudget(3, fake_clock)
    assert budget.consume() == 2

    fake_clock.t = T0
    assert budget.remaining() == 2
    assert budget.snapshot() == BudgetState(DAY1, 1)


def test_b6_zero_and_negative_cap(fake_clock):
    fake_clock.t = T0
    budget = DailyBudget(0, fake_clock)
    assert budget.would_exceed() is True
    with pytest.raises(BudgetExceededError):
        budget.consume()

    with pytest.raises(PricingPolicyError) as excinfo:
        DailyBudget(-1, fake_clock)
    assert excinfo.value.code == "BUDGET_CONFIG_INVALID"


def test_budget_exceeded_error_attrs(fake_clock):
    fake_clock.t = T0
    budget = DailyBudget(0, fake_clock)
    try:
        budget.consume()
    except BudgetExceededError as exc:
        assert not isinstance(exc, ValueError)
        assert isinstance(exc, EstimatorError)
    else:
        raise AssertionError("expected BudgetExceededError")
