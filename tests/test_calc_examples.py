from decimal import Decimal

from codey_estimator.calc import CALC_ENGINE_VERSION, calculate
from codey_estimator.dto import (
    DiscountKind,
    EstimateDiscount,
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


def test_example_a_hourly_material_waste_packages():
    estimate = EstimateInput(
        lines=(_example_a_line(),),
        tax_rate_bp=635,
        tax_method=TaxMethod.MATERIALS_ONLY,
    )
    result = calculate(estimate)
    line = result.lines[0]

    assert line.qty_with_waste == Decimal("198")
    assert line.packages_needed == 4
    assert line.material_cost_cents == 12988
    assert line.material_sell_cents == 17859
    assert line.labor_cost_cents == 13500
    assert line.labor_sell_cents == 28500
    assert line.cost_total_cents == 26488
    assert line.components_sell_cents == 46359
    assert line.sell_total_cents == 46359

    assert result.subtotal_sell_cents == 46359
    assert result.discount_cents == 0
    assert line.allocated_discount_cents == 0
    assert line.net_sell_cents == 46359
    assert line.taxable_amount_cents == 17859
    assert result.taxable_base_cents == 17859
    assert result.tax_cents == 1134
    assert line.tax_cents == 1134
    assert line.line_total_cents == 47493
    assert result.total_cents == 47493
    assert result.gross_profit_cents == 19871
    assert result.gross_margin_bp == 4286
    assert result.markup_effective_bp == 7502
    assert result.warnings == ()
    assert result.calc_engine_version == 1


def test_example_a_taxable_lines_contrast():
    estimate = EstimateInput(
        lines=(_example_a_line(),),
        tax_rate_bp=635,
        tax_method=TaxMethod.TAXABLE_LINES,
    )
    result = calculate(estimate)
    assert result.taxable_base_cents == 46359
    assert result.tax_cents == 2944


def test_example_c_discount_materials_only_tax():
    line_c1 = LineInput(
        line_key="C1",
        line_type=LineType.MATERIAL,
        description="drywall sheets",
        customer_description="Drywall sheets",
        material=MaterialInput(
            quantity=Decimal("42"),
            unit="SH",
            unit_cost_cents=1598,
            package_qty=Decimal("1"),
            waste_pct_bp=1000,
            material_markup_bp=3000,
        ),
    )
    line_c2 = LineInput(
        line_key="C2",
        line_type=LineType.LABOR,
        description="hang drywall",
        customer_description="Hang drywall",
        labor=LaborInput(
            rate_type=LaborRateType.HOURLY,
            labor_qty=Decimal("16"),
            labor_unit="HR",
            labor_cost_rate_cents=3800,
            labor_bill_rate_cents=7500,
        ),
    )
    estimate = EstimateInput(
        lines=(line_c1, line_c2),
        tax_rate_bp=635,
        tax_method=TaxMethod.MATERIALS_ONLY,
        estimate_discount=EstimateDiscount(kind=DiscountKind.PERCENT, value=500),
    )
    result = calculate(estimate)
    c1, c2 = result.lines

    assert c1.material_cost_cents == 75106
    assert c1.material_sell_cents == 97638
    assert c1.sell_total_cents == 97638

    assert c2.labor_cost_cents == 60800
    assert c2.labor_sell_cents == 120000

    assert result.subtotal_sell_cents == 217638
    assert result.discount_cents == 10882

    assert c1.allocated_discount_cents == 4882
    assert c2.allocated_discount_cents == 6000

    assert c1.net_sell_cents == 92756
    assert c2.net_sell_cents == 114000

    assert c1.taxable_amount_cents == 92756
    assert c2.taxable_amount_cents == 0
    assert result.taxable_base_cents == 92756
    assert result.tax_cents == 5890

    assert c1.tax_cents == 5890
    assert c2.tax_cents == 0
    assert c1.line_total_cents == 98646
    assert c2.line_total_cents == 114000
    assert result.total_cents == 212646

    assert result.cost_total_cents == 135906
    assert result.gross_profit_cents == 70850
    assert result.gross_margin_bp == 3427
    assert result.markup_effective_bp == 5213


def _example_c_estimate(margin_floor_bp):
    line_c1 = LineInput(
        line_key="C1",
        line_type=LineType.MATERIAL,
        description="drywall sheets",
        customer_description="Drywall sheets",
        material=MaterialInput(
            quantity=Decimal("42"),
            unit="SH",
            unit_cost_cents=1598,
            package_qty=Decimal("1"),
            waste_pct_bp=1000,
            material_markup_bp=3000,
        ),
    )
    line_c2 = LineInput(
        line_key="C2",
        line_type=LineType.LABOR,
        description="hang drywall",
        customer_description="Hang drywall",
        labor=LaborInput(
            rate_type=LaborRateType.HOURLY,
            labor_qty=Decimal("16"),
            labor_unit="HR",
            labor_cost_rate_cents=3800,
            labor_bill_rate_cents=7500,
        ),
    )
    return EstimateInput(
        lines=(line_c1, line_c2),
        tax_rate_bp=635,
        tax_method=TaxMethod.MATERIALS_ONLY,
        estimate_discount=EstimateDiscount(kind=DiscountKind.PERCENT, value=500),
        margin_floor_bp=margin_floor_bp,
    )


def test_example_c_margin_floor_warning():
    result_below = calculate(_example_c_estimate(3500))
    assert result_below.warnings == ("MARGIN_BELOW_FLOOR",)

    result_at = calculate(_example_c_estimate(3427))
    assert result_at.warnings == ()

    result_none = calculate(_example_c_estimate(None))
    assert result_none.warnings == ()


def test_example_d_combined_line_discount_tax_share():
    line = _example_a_line(line_key="D1", line_discount_cents=1359)
    estimate = EstimateInput(
        lines=(line,),
        tax_rate_bp=635,
        tax_method=TaxMethod.MATERIALS_ONLY,
    )
    result = calculate(estimate)
    line_result = result.lines[0]

    assert line_result.sell_before_discount_cents == 46359
    assert line_result.sell_total_cents == 45000
    assert line_result.taxable_amount_cents == 17335
    assert result.tax_cents == 1101
    assert result.total_cents == 46101
    assert result.cost_total_cents == 26488
    assert result.gross_profit_cents == 18512
    assert result.gross_margin_bp == 4114
    assert result.markup_effective_bp == 6989


def test_engine_version():
    assert CALC_ENGINE_VERSION == 1
    estimate = EstimateInput(lines=(), tax_rate_bp=635)
    result = calculate(estimate)
    assert result.calc_engine_version == 1
