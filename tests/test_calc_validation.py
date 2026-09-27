import copy
from decimal import Decimal

import pytest

from codey_estimator.calc import calculate
from codey_estimator.dto import (
    DiscountKind,
    EstimateDiscount,
    EstimateInput,
    EquipmentInput,
    LaborInput,
    LaborRateType,
    LineInput,
    LineType,
    MaterialInput,
)
from codey_estimator.errors import EstimateValidationError


def _material(**overrides):
    defaults = dict(
        quantity=Decimal("10"),
        unit="SF",
        unit_cost_cents=100,
        package_qty=Decimal("1"),
        material_markup_bp=0,
        waste_pct_bp=0,
    )
    defaults.update(overrides)
    return MaterialInput(**defaults)


def _material_line(**overrides):
    defaults = dict(
        line_key="M1",
        line_type=LineType.MATERIAL,
        description="material",
        customer_description="Material",
        material=_material(),
    )
    defaults.update(overrides)
    return LineInput(**defaults)


def _estimate(lines, **overrides):
    defaults = dict(tax_rate_bp=635)
    defaults.update(overrides)
    return EstimateInput(lines=tuple(lines), **defaults)


def test_blank_line_key():
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([_material_line(line_key="")]))
    assert exc.value.code == "BLANK_LINE_KEY"
    assert exc.value.line_key == ""


def test_duplicate_line_key():
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([_material_line(line_key="A"), _material_line(line_key="A")]))
    assert exc.value.code == "DUPLICATE_LINE_KEY"
    assert exc.value.line_key == "A"


def test_line_type_mismatch():
    line = _material_line(line_type=LineType.LABOR)
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "LINE_TYPE_MISMATCH"
    assert exc.value.line_key == "M1"


def test_negative_quantity():
    line = _material_line(material=_material(quantity=Decimal("-1")))
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "NEGATIVE_QUANTITY"
    assert exc.value.line_key == "M1"


def test_invalid_package_qty():
    line = _material_line(material=_material(package_qty=Decimal("0.5")))
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "INVALID_PACKAGE_QTY"
    assert exc.value.line_key == "M1"


def test_negative_amount():
    line = _material_line(material=_material(unit_cost_cents=-1))
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "NEGATIVE_AMOUNT"
    assert exc.value.line_key == "M1"


def test_invalid_bp():
    line = _material_line(material=_material(waste_pct_bp=10001))
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "INVALID_BP"
    assert exc.value.line_key == "M1"


def test_unknown_unit():
    line = _material_line(material=_material(unit="furlong"))
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "UNKNOWN_UNIT"
    assert exc.value.line_key == "M1"


def test_incompatible_units():
    line = _material_line(material=_material(unit="SF", package_unit="LF"))
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "INCOMPATIBLE_UNITS"
    assert exc.value.line_key == "M1"


def test_labor_unit_mismatch():
    line = LineInput(
        line_key="L1",
        line_type=LineType.LABOR,
        description="labor",
        customer_description="Labor",
        labor=LaborInput(
            rate_type=LaborRateType.HOURLY,
            labor_qty=Decimal("1"),
            labor_unit="ROOM",
            labor_cost_rate_cents=100,
            labor_bill_rate_cents=200,
        ),
    )
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "LABOR_UNIT_MISMATCH"
    assert exc.value.line_key == "L1"


def test_override_reason_required():
    line = _material_line(price_override_cents=500)
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "OVERRIDE_REASON_REQUIRED"
    assert exc.value.line_key == "M1"


def test_negative_line_sell():
    line = _material_line(line_discount_cents=999999)
    with pytest.raises(EstimateValidationError) as exc:
        calculate(_estimate([line]))
    assert exc.value.code == "NEGATIVE_LINE_SELL"
    assert exc.value.line_key == "M1"


def test_fixed_discount_exceeds_subtotal():
    line = _material_line()
    estimate = _estimate(
        [line], estimate_discount=EstimateDiscount(kind=DiscountKind.FIXED, value=999999)
    )
    with pytest.raises(EstimateValidationError) as exc:
        calculate(estimate)
    assert exc.value.code == "DISCOUNT_EXCEEDS_SUBTOTAL"


def test_float_quantity_type_error():
    line = _material_line(material=_material(quantity=10.0))
    with pytest.raises(TypeError):
        calculate(_estimate([line]))


def test_bool_money_type_error():
    line = _material_line(material=_material(unit_cost_cents=True))
    with pytest.raises(TypeError):
        calculate(_estimate([line]))


def test_percent_discount_10000_bp_gives_zero_net():
    line = _material_line()
    estimate = _estimate(
        [line], estimate_discount=EstimateDiscount(kind=DiscountKind.PERCENT, value=10000)
    )
    result = calculate(estimate)
    assert result.gross_margin_bp == 0
    assert result.warnings == ()


def test_empty_estimate_all_zero():
    result = calculate(_estimate([]))
    assert result.subtotal_sell_cents == 0
    assert result.total_cents == 0
    assert result.gross_margin_bp == 0
    assert result.markup_effective_bp is None


def test_line_discount_equal_to_sell_ok():
    line = _material_line(material=_material(unit_cost_cents=100), line_discount_cents=1000)
    result = calculate(_estimate([line]))
    assert result.lines[0].sell_total_cents == 0
