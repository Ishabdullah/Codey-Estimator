from decimal import Decimal

import pytest

from codey_estimator.money import (
    allocate_pro_rata,
    apply_markup,
    format_cents,
    parse_dollars,
    percent_of,
    ratio_bp,
    round_half_up,
)


def test_round_half_up_table():
    assert round_half_up(Decimal("17858.5")) == 17859
    assert round_half_up(Decimal("2.5")) == 3
    assert round_half_up(Decimal("-2.5")) == -3
    assert round_half_up(Decimal("2.4999")) == 2
    assert round_half_up(Decimal("1134.0465")) == 1134
    assert round_half_up(Decimal("0")) == 0


def test_round_half_up_rejects_float():
    with pytest.raises(TypeError):
        round_half_up(2.5)


def test_apply_markup():
    assert apply_markup(12988, 3750) == 17859
    assert apply_markup(75106, 3000) == 97638
    with pytest.raises(ValueError):
        apply_markup(-1, 0)
    with pytest.raises(ValueError):
        apply_markup(0, -1)


def test_percent_of():
    assert percent_of(217638, 500) == 10882
    assert percent_of(17859, 635) == 1134


def test_ratio_bp():
    assert ratio_bp(19871, 46359) == 4286
    assert ratio_bp(-100, 1000) == -1000
    with pytest.raises(ZeroDivisionError):
        ratio_bp(100, 0)


def test_allocate_pro_rata_cases():
    assert allocate_pro_rata(10882, [97638, 120000]) == [4882, 6000]
    assert allocate_pro_rata(1, [1, 1]) == [1, 0]
    assert allocate_pro_rata(2, [1, 1, 1]) == [1, 1, 0]
    assert allocate_pro_rata(10, [1, 1, 1]) == [4, 3, 3]
    assert allocate_pro_rata(100, [3333, 3333, 3334]) == [33, 33, 34]
    assert allocate_pro_rata(0, [0, 0]) == [0, 0]
    with pytest.raises(ValueError):
        allocate_pro_rata(5, [0, 0])
    assert allocate_pro_rata(0, []) == []
    with pytest.raises(ValueError):
        allocate_pro_rata(-1, [1, 1])
    with pytest.raises(ValueError):
        allocate_pro_rata(10, [-1, 1])


def test_parse_dollars_valid_and_invalid():
    assert parse_dollars("12") == 1200
    assert parse_dollars("12.3") == 1230
    assert parse_dollars("-0.05") == -5
    with pytest.raises(ValueError):
        parse_dollars("12.345")
    with pytest.raises(ValueError):
        parse_dollars("$12")
    with pytest.raises(ValueError):
        parse_dollars("1,000")
    with pytest.raises(ValueError):
        parse_dollars("")
    with pytest.raises(TypeError):
        parse_dollars(12)


def test_format_cents():
    assert format_cents(123456) == "$1,234.56"
    assert format_cents(0) == "$0.00"
    assert format_cents(-150) == "-$1.50"
    assert format_cents(5) == "$0.05"
