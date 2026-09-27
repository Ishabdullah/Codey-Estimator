from decimal import Decimal

from codey_estimator.calc import calculate
from codey_estimator.dto import (
    EstimateInput,
    LaborInput,
    LaborRateType,
    LineInput,
    LineType,
    MaterialInput,
    TaxMethod,
)


def _example_a_line(**overrides):
    material = MaterialInput(
        quantity=Decimal("180"),
        unit="LF",
        unit_cost_cents=3247,
        package_qty=Decimal("50"),
        package_unit="FT",
        waste_pct_bp=1000,
        material_markup_bp=3750,
    )
    labor = LaborInput(
        rate_type=LaborRateType.HOURLY,
        labor_qty=Decimal("3"),
        labor_unit="HR",
        labor_cost_rate_cents=4500,
        labor_bill_rate_cents=9500,
        labor_type="plumber",
    )
    defaults = dict(
        line_key="A1",
        line_type=LineType.COMBINED,
        description="PEX + plumber",
        customer_description="PEX repipe with plumber labor",
        material=material,
        labor=labor,
    )
    defaults.update(overrides)
    return LineInput(**defaults)


def test_none_method_zero_tax():
    estimate = EstimateInput(
        lines=(_example_a_line(),), tax_rate_bp=635, tax_method=TaxMethod.NONE
    )
    result = calculate(estimate)
    assert result.tax_cents == 0
    assert result.total_cents == 46359


def test_taxable_false_line_excluded_all_methods():
    for method in (TaxMethod.NONE, TaxMethod.TAXABLE_LINES, TaxMethod.MATERIALS_ONLY):
        line = _example_a_line(taxable=False)
        estimate = EstimateInput(lines=(line,), tax_rate_bp=635, tax_method=method)
        result = calculate(estimate)
        assert result.tax_cents == 0


def test_materials_only_labor_only_line_untaxed():
    line = LineInput(
        line_key="B1",
        line_type=LineType.LABOR,
        description="drywall hang",
        customer_description="Drywall hang",
        labor=LaborInput(
            rate_type=LaborRateType.FIXED_FLAT,
            labor_qty=Decimal("3"),
            labor_unit="ROOM",
            labor_cost_rate_cents=40000,
            labor_bill_rate_cents=85000,
            labor_type="drywall hang",
        ),
        taxable=True,
    )
    estimate = EstimateInput(lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.MATERIALS_ONLY)
    result = calculate(estimate)
    assert result.lines[0].taxable_amount_cents == 0
    assert result.tax_cents == 0


def test_override_line_materials_only_uses_component_ratio():
    line = _example_a_line(price_override_cents=50000, override_reason="negotiated")
    estimate = EstimateInput(lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.MATERIALS_ONLY)
    result = calculate(estimate)
    line_result = result.lines[0]
    assert line_result.taxable_amount_cents == 19262
    assert result.tax_cents == 1223
    assert result.cost_total_cents == 26488


def test_allowance_override_only_materials_only_untaxed():
    line = LineInput(
        line_key="ALLOW1",
        line_type=LineType.ALLOWANCE,
        description="allowance",
        customer_description="Allowance",
        price_override_cents=10000,
        override_reason="flat allowance",
    )
    estimate_materials_only = EstimateInput(
        lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.MATERIALS_ONLY
    )
    result = calculate(estimate_materials_only)
    assert result.lines[0].taxable_amount_cents == 0

    estimate_taxable_lines = EstimateInput(
        lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.TAXABLE_LINES
    )
    result2 = calculate(estimate_taxable_lines)
    assert result2.lines[0].taxable_amount_cents == result2.lines[0].net_sell_cents
