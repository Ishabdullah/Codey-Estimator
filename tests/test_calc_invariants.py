import copy
import random
from decimal import Decimal

from codey_estimator.calc import calculate
from codey_estimator.calc.engine import calculate_line
from codey_estimator.dto import (
    DiscountKind,
    EquipmentInput,
    EstimateDiscount,
    EstimateInput,
    LaborInput,
    LaborRateType,
    LineInput,
    LineType,
    MaterialInput,
    SubcontractorInput,
    TaxMethod,
)


def _random_material(rng: random.Random) -> MaterialInput:
    unit = rng.choice(["SF", "LF", "EA", "GAL", "CF"])
    return MaterialInput(
        quantity=Decimal(rng.randint(1, 500)),
        unit=unit,
        unit_cost_cents=rng.randint(1, 10000),
        package_qty=Decimal(rng.randint(1, 20)),
        waste_pct_bp=rng.randint(0, 3000),
        material_markup_bp=rng.randint(0, 5000),
    )


def _random_labor(rng: random.Random) -> LaborInput:
    rate_type = rng.choice(list(LaborRateType))
    if rate_type == LaborRateType.HOURLY:
        unit = "HR"
    elif rate_type == LaborRateType.FIXED_PER_UNIT:
        unit = rng.choice(["ROOM", "FIXTURE", "EA"])
    else:
        unit = rng.choice(["HR", "ROOM", "FIXTURE", "EA"])
    return LaborInput(
        rate_type=rate_type,
        labor_qty=Decimal(rng.randint(0, 40)),
        labor_unit=unit,
        labor_cost_rate_cents=rng.randint(0, 10000),
        labor_bill_rate_cents=rng.randint(0, 20000),
    )


def _random_equipment(rng: random.Random) -> EquipmentInput:
    return EquipmentInput(
        equipment_cost_cents=rng.randint(0, 5000), equipment_markup_bp=rng.randint(0, 5000)
    )


def _random_sub(rng: random.Random) -> SubcontractorInput:
    return SubcontractorInput(
        sub_cost_cents=rng.randint(0, 20000), sub_markup_bp=rng.randint(0, 5000)
    )


def _random_line(rng: random.Random, idx: int) -> LineInput:
    choices = ["material", "labor", "equipment", "subcontractor"]
    chosen = [c for c in choices if rng.random() < 0.5]
    if not chosen:
        chosen = [rng.choice(choices)]
    kwargs = {}
    if "material" in chosen:
        kwargs["material"] = _random_material(rng)
    if "labor" in chosen:
        kwargs["labor"] = _random_labor(rng)
    if "equipment" in chosen:
        kwargs["equipment"] = _random_equipment(rng)
    if "subcontractor" in chosen:
        kwargs["subcontractor"] = _random_sub(rng)

    if len(chosen) == 1:
        line_type = {
            "material": LineType.MATERIAL,
            "labor": LineType.LABOR,
            "equipment": LineType.EQUIPMENT,
            "subcontractor": LineType.SUBCONTRACTOR,
        }[chosen[0]]
    else:
        line_type = LineType.COMBINED

    return LineInput(
        line_key=f"L{idx}",
        line_type=line_type,
        description=f"line {idx}",
        customer_description=f"Line {idx}",
        taxable=rng.random() < 0.8,
        **kwargs,
    )


def _random_estimate(rng: random.Random) -> EstimateInput:
    num_lines = rng.randint(0, 8)
    lines = tuple(_random_line(rng, i) for i in range(num_lines))

    subtotal = sum(calculate_line(line).sell_total_cents for line in lines)

    discount = None
    if rng.random() < 0.5:
        if rng.random() < 0.5:
            discount = EstimateDiscount(kind=DiscountKind.PERCENT, value=rng.randint(0, 10000))
        else:
            discount = EstimateDiscount(
                kind=DiscountKind.FIXED, value=rng.randint(0, subtotal) if subtotal else 0
            )

    return EstimateInput(
        lines=lines,
        tax_rate_bp=rng.randint(0, 2000),
        tax_method=rng.choice(list(TaxMethod)),
        estimate_discount=discount,
    )


def test_randomized_invariants():
    rng = random.Random(20260927)
    for _ in range(500):
        estimate = _random_estimate(rng)
        result = calculate(estimate)

        assert sum(line.line_total_cents for line in result.lines) == result.total_cents
        assert (
            sum(line.allocated_discount_cents for line in result.lines) == result.discount_cents
        )
        assert sum(line.tax_cents for line in result.lines) == result.tax_cents
        assert (
            result.total_cents
            == result.subtotal_sell_cents - result.discount_cents + result.tax_cents
        )
        assert result.cost_total_cents == (
            result.material_cost_cents
            + result.labor_cost_cents
            + result.equipment_cost_cents
            + result.sub_cost_cents
        )
        for line in result.lines:
            assert line.net_sell_cents >= 0


def test_deterministic():
    material = MaterialInput(
        quantity=Decimal("100"),
        unit="SF",
        unit_cost_cents=250,
        package_qty=Decimal("10"),
        waste_pct_bp=500,
        material_markup_bp=2000,
    )
    line = LineInput(
        line_key="D1",
        line_type=LineType.MATERIAL,
        description="det",
        customer_description="Det",
        material=material,
    )
    estimate = EstimateInput(lines=(line,), tax_rate_bp=635)
    snapshot = copy.deepcopy(estimate)

    result1 = calculate(estimate)
    result2 = calculate(estimate)

    assert result1 == result2
    assert estimate == snapshot
