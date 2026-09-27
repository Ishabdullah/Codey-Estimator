from decimal import Decimal

import pytest

from codey_estimator.calc import calculate
from codey_estimator.dto import (
    EstimateInput,
    LaborInput,
    LaborRateType,
    LineInput,
    LineType,
    TaxMethod,
)


def _labor_line(rate_type, labor_qty, **overrides):
    labor = LaborInput(
        rate_type=rate_type,
        labor_qty=labor_qty,
        labor_unit=overrides.pop("labor_unit", "ROOM"),
        labor_cost_rate_cents=overrides.pop("labor_cost_rate_cents", 40000),
        labor_bill_rate_cents=overrides.pop("labor_bill_rate_cents", 85000),
        labor_type="drywall hang",
    )
    defaults = dict(
        line_key="B1",
        line_type=LineType.LABOR,
        description="drywall hang",
        customer_description="Drywall hang",
        labor=labor,
        taxable=True,
    )
    defaults.update(overrides)
    return LineInput(**defaults)


def _calc_single(line):
    estimate = EstimateInput(lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.MATERIALS_ONLY)
    return calculate(estimate)


def test_fixed_flat_ignores_qty():
    result = _calc_single(_labor_line(LaborRateType.FIXED_FLAT, Decimal("3")))
    line = result.lines[0]
    assert line.labor_cost_cents == 40000
    assert line.labor_sell_cents == 85000
    assert line.cost_total_cents == 40000
    assert line.sell_total_cents == 85000
    assert line.taxable_amount_cents == 0
    assert result.tax_cents == 0
    assert result.total_cents == 85000
    assert result.gross_profit_cents == 45000
    assert result.gross_margin_bp == 5294
    assert result.markup_effective_bp == 11250


def test_fixed_per_unit_multiplies():
    line = _labor_line(
        LaborRateType.FIXED_PER_UNIT, Decimal("3"), labor_unit="ROOM"
    )
    result = _calc_single(line)
    line_result = result.lines[0]
    assert line_result.labor_cost_cents == 120000
    assert line_result.labor_sell_cents == 255000
    assert result.gross_profit_cents == 135000
    assert result.gross_margin_bp == 5294
    assert result.markup_effective_bp == 11250


def test_fixed_flat_zero_qty_still_charges_cost_and_sell():
    result = _calc_single(_labor_line(LaborRateType.FIXED_FLAT, Decimal("0")))
    line = result.lines[0]
    assert line.labor_cost_cents == 40000
    assert line.labor_sell_cents == 85000


def test_hourly_fractional_qty():
    line = LineInput(
        line_key="H1",
        line_type=LineType.LABOR,
        description="hourly fractional",
        customer_description="Hourly fractional",
        labor=LaborInput(
            rate_type=LaborRateType.HOURLY,
            labor_qty=Decimal("2.5"),
            labor_unit="HR",
            labor_cost_rate_cents=4500,
            labor_bill_rate_cents=9500,
        ),
    )
    result = _calc_single(line)
    line_result = result.lines[0]
    assert line_result.labor_cost_cents == 11250
    assert line_result.labor_sell_cents == 23750


def test_hourly_half_cent_rounding():
    line = LineInput(
        line_key="H2",
        line_type=LineType.LABOR,
        description="half cent rounding",
        customer_description="Half cent rounding",
        labor=LaborInput(
            rate_type=LaborRateType.HOURLY,
            labor_qty=Decimal("0.5"),
            labor_unit="HR",
            labor_cost_rate_cents=4501,
            labor_bill_rate_cents=9500,
        ),
    )
    result = _calc_single(line)
    line_result = result.lines[0]
    assert line_result.labor_cost_cents == 2251


def test_no_markup_fallback():
    with pytest.raises(TypeError):
        LaborInput(
            rate_type=LaborRateType.HOURLY,
            labor_qty=Decimal("1"),
            labor_unit="HR",
            labor_cost_rate_cents=1000,
        )
