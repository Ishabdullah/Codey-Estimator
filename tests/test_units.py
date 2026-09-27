from decimal import Decimal
from fractions import Fraction

import pytest

from codey_estimator.errors import IncompatibleUnitsError, UnknownUnitError
from codey_estimator.units import convert_quantity, normalize_unit, packages_needed


def test_normalize_aliases():
    assert normalize_unit("hr") == "HR"
    assert normalize_unit("Hours") == "HR"
    assert normalize_unit(" sq ft ") == "SF"
    assert normalize_unit("each") == "EA"


def test_unknown_unit():
    with pytest.raises(UnknownUnitError):
        normalize_unit("furlong")


def test_convert_exact():
    assert convert_quantity(Decimal("12"), "IN", "FT") == Fraction(1)
    assert convert_quantity(Decimal("24.725"), "SQ", "SF") == Fraction(4945, 2)
    assert convert_quantity(Decimal("1"), "CY", "CF") == Fraction(27)
    assert convert_quantity(Decimal("10"), "LF", "FT") == Fraction(10)
    assert convert_quantity(Decimal("10"), "FT", "LF") == Fraction(10)


def test_convert_incompatible():
    with pytest.raises(IncompatibleUnitsError):
        convert_quantity(Decimal("1"), "SF", "LF")
    with pytest.raises(IncompatibleUnitsError):
        convert_quantity(Decimal("1"), "BX", "EA")


def test_packages_needed():
    assert packages_needed(Decimal("198"), "LF", Decimal("50"), "FT") == 4
    assert packages_needed(Decimal("200"), "FT", Decimal("50"), "FT") == 4
    assert packages_needed(Decimal("24.725"), "SQ", Decimal("33.3"), "SF") == 75
    assert packages_needed(Decimal("0"), "EA", Decimal("1"), "EA") == 0
    with pytest.raises(ValueError):
        packages_needed(Decimal("1"), "EA", Decimal("0"), "EA")


def test_float_trap():
    from codey_estimator.calc.engine import calculate_line
    from codey_estimator.dto import LineInput, LineType, MaterialInput

    line = LineInput(
        line_key="float-trap",
        line_type=LineType.MATERIAL,
        description="float trap material",
        material=MaterialInput(
            quantity=Decimal("110"),
            unit="FT",
            unit_cost_cents=100,
            package_qty=Decimal("1"),
            package_unit="FT",
            waste_pct_bp=1000,
        ),
    )
    result = calculate_line(line)
    assert result.packages_needed == 121
