from fractions import Fraction

import pytest

from codey_estimator.catalog.schema import Measure
from codey_estimator.catalog.text import (
    find_measures,
    format_measure_value,
    parse_fraction,
    preprocess,
)


def test_preprocess_examples():
    assert preprocess('Apollo ½" x 50\' Red PEX B Tubing') == (
        "apollo 1/2 in x 50 ft red pex b tubing"
    )
    assert preprocess('1½" Copper') == "1-1/2 in copper"
    assert preprocess("Box of 1,000") == "box of 1000"
    assert preprocess("Lowe's 3/4″ × 10′ pipe") == "lowe's 3/4 in x 10 ft pipe"


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("1/2", Fraction(1, 2)),
        ("½", Fraction(1, 2)),
        ("0.5", Fraction(1, 2)),
        (".5", Fraction(1, 2)),
        ("1-5/8", Fraction(13, 8)),
        ("1 5/8", Fraction(13, 8)),
        ("1½", Fraction(3, 2)),
        ("50", Fraction(50)),
        ("2.50", Fraction(5, 2)),
    ],
)
def test_parse_fraction_forms(token, expected):
    assert parse_fraction(token) == expected


@pytest.mark.parametrize("bad", ["", "abc", "1/0", "1//2", "-1/2"])
def test_parse_fraction_rejects(bad):
    with pytest.raises(ValueError):
        parse_fraction(bad)


def test_find_measures_order_and_units():
    result = find_measures("2 in. x 4 in. x 8 ft.")
    assert [m for m, _ in result] == [
        Measure(Fraction(2), "IN"),
        Measure(Fraction(4), "IN"),
        Measure(Fraction(8), "FT"),
    ]
    result = find_measures("1 qt. and 5-gal")
    assert [m for m, _ in result] == [
        Measure(Fraction(1), "QT"),
        Measure(Fraction(5), "GAL"),
    ]


def test_find_measures_skips_zero_and_zero_denominator():
    result = find_measures("0 ft 1/0 in 3 ft")
    assert [m for m, _ in result] == [Measure(Fraction(3), "FT")]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Fraction(1, 2), "0.5"),
        (Fraction(50), "50"),
        (Fraction(13, 8), "1.625"),
        (Fraction(247, 32), "7.71875"),
        (Fraction(25, 3), "25/3"),
        (Fraction(1, 4), "0.25"),
    ],
)
def test_format_measure_value(value, expected):
    assert format_measure_value(value) == expected
