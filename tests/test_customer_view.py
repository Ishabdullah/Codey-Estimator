import json
from dataclasses import fields
from decimal import Decimal

import pytest

from codey_estimator.calc import calculate
from codey_estimator.dto import (
    CUSTOMER_LINE_KEYS,
    CUSTOMER_VIEW_KEYS,
    CustomerEstimateView,
    CustomerLineView,
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
    to_customer_view,
)
from codey_estimator.errors import CustomerViewError

FORBIDDEN_SUBSTRINGS = [
    "cost",
    "markup",
    "margin",
    "profit",
    "waste",
    "retailer",
    "sku",
    "observation",
    "internal",
    "rate",
    "override",
    "package",
    "allocated",
    "taxable",
    "engine",
    "labor",
    "equipment",
    "sub_",
    "note_",
]

SENTINELS = [
    "INTERNAL-DESC-SENTINEL",
    "SECRET-NOTE-SENTINEL",
    "SKU-SENTINEL-123",
    "PRODUCT-TITLE-SENTINEL",
    "OVERRIDE-SENTINEL",
    "LABORTYPE-SENTINEL",
    "SECTION-SENTINEL",
    "CATEGORY-SENTINEL",
]
SENTINEL_IDS = [987654]


def _full_estimate():
    material = MaterialInput(
        quantity=Decimal("10"),
        unit="SF",
        unit_cost_cents=500,
        package_qty=Decimal("1"),
        waste_pct_bp=1000,
        material_markup_bp=2000,
        price_book_item_id=987654,
        retailer_product_id=987654,
        price_observation_id=987654,
        retailer_code_snapshot="SKU-SENTINEL-123",
        product_title_snapshot="PRODUCT-TITLE-SENTINEL",
    )
    labor = LaborInput(
        rate_type=LaborRateType.HOURLY,
        labor_qty=Decimal("2"),
        labor_unit="HR",
        labor_cost_rate_cents=1000,
        labor_bill_rate_cents=2000,
        labor_type="LABORTYPE-SENTINEL",
        labor_rate_id=987654,
    )
    equipment = EquipmentInput(
        equipment_cost_cents=300, equipment_markup_bp=1000, equipment_id=987654
    )
    subcontractor = SubcontractorInput(
        sub_cost_cents=400, sub_markup_bp=500, subcontractor_id=987654
    )
    visible_line = LineInput(
        line_key="V1",
        line_type=LineType.COMBINED,
        description="INTERNAL-DESC-SENTINEL",
        customer_description="Visible line for customer",
        visible_to_customer=True,
        sort_order=1,
        section="SECTION-SENTINEL",
        category="CATEGORY-SENTINEL",
        material=material,
        labor=labor,
        equipment=equipment,
        subcontractor=subcontractor,
        line_discount_cents=100,
        price_override_cents=None,
        internal_note="SECRET-NOTE-SENTINEL",
    )
    override_line = LineInput(
        line_key="V2",
        line_type=LineType.ALLOWANCE,
        description="INTERNAL-DESC-SENTINEL",
        customer_description="Allowance for customer",
        visible_to_customer=True,
        sort_order=0,
        price_override_cents=5000,
        override_reason="OVERRIDE-SENTINEL",
        internal_note="SECRET-NOTE-SENTINEL",
    )
    hidden_line = LineInput(
        line_key="H1",
        line_type=LineType.MATERIAL,
        description="INTERNAL-DESC-SENTINEL",
        customer_description="",
        visible_to_customer=False,
        material=MaterialInput(
            quantity=Decimal("5"),
            unit="SF",
            unit_cost_cents=100,
        ),
    )
    return EstimateInput(
        lines=(visible_line, override_line, hidden_line),
        tax_rate_bp=635,
        tax_method=TaxMethod.MATERIALS_ONLY,
        estimate_discount=EstimateDiscount(kind=DiscountKind.PERCENT, value=500),
        terms="Net 30",
        customer_notes="Thanks for your business",
    )


def _collect_keys(obj, keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            _collect_keys(v, keys)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys(item, keys)


def test_forbidden_keys_absent():
    result = calculate(_full_estimate())
    view = to_customer_view(result)
    data = view.to_dict()

    assert set(data.keys()) == CUSTOMER_VIEW_KEYS
    for line in data["lines"]:
        assert set(line.keys()) == CUSTOMER_LINE_KEYS

    all_keys: set = set()
    _collect_keys(data, all_keys)
    for key in all_keys:
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden == "customer_notes" and key == "customer_notes":
                continue
            assert forbidden not in key, f"key {key!r} contains forbidden substring {forbidden!r}"

    dumped = json.dumps(data)
    for sentinel in SENTINELS:
        assert sentinel not in dumped
    for sentinel_id in SENTINEL_IDS:
        assert str(sentinel_id) not in dumped


def test_customer_view_dataclass_fields_exact():
    assert {f.name for f in fields(CustomerEstimateView)} == {
        "lines",
        "subtotal_cents",
        "discount_cents",
        "tax_cents",
        "total_cents",
        "terms",
        "customer_notes",
    }
    assert {f.name for f in fields(CustomerLineView)} == {
        "description",
        "quantity",
        "unit",
        "price_cents",
    }


def test_hidden_line_excluded_totals_unchanged():
    estimate = _full_estimate()
    result = calculate(estimate)
    view = to_customer_view(result)
    assert len(view.lines) == 2
    assert view.total_cents == result.total_cents
    assert view.subtotal_cents == result.subtotal_sell_cents


def test_sort_order_stable():
    estimate = _full_estimate()
    result = calculate(estimate)
    view = to_customer_view(result)
    descriptions = [line.description for line in view.lines]
    assert descriptions == ["Allowance for customer", "Visible line for customer"]


def test_missing_customer_description_raises():
    line = LineInput(
        line_key="X1",
        line_type=LineType.MATERIAL,
        description="internal",
        customer_description="",
        visible_to_customer=True,
        material=MaterialInput(quantity=Decimal("1"), unit="EA", unit_cost_cents=100),
    )
    estimate = EstimateInput(lines=(line,), tax_rate_bp=0)
    result = calculate(estimate)
    with pytest.raises(CustomerViewError) as exc:
        to_customer_view(result)
    assert exc.value.code == "MISSING_CUSTOMER_DESCRIPTION"
    assert exc.value.line_key == "X1"


def test_quantity_formatting():
    line1 = LineInput(
        line_key="Q1",
        line_type=LineType.MATERIAL,
        description="q1",
        customer_description="Q1",
        material=MaterialInput(quantity=Decimal("100"), unit="EA", unit_cost_cents=100),
    )
    line2 = LineInput(
        line_key="Q2",
        line_type=LineType.MATERIAL,
        description="q2",
        customer_description="Q2",
        material=MaterialInput(quantity=Decimal("2.50"), unit="EA", unit_cost_cents=100),
    )
    line3 = LineInput(
        line_key="Q3",
        line_type=LineType.MATERIAL,
        description="q3",
        customer_description="Q3",
        material=MaterialInput(quantity=Decimal("3.00"), unit="EA", unit_cost_cents=100),
    )
    estimate = EstimateInput(lines=(line1, line2, line3), tax_rate_bp=0)
    result = calculate(estimate)
    view = to_customer_view(result)
    quantities = [line.quantity for line in view.lines]
    assert quantities == ["100", "2.5", "3"]


def test_example_a_view():
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
    line = LineInput(
        line_key="A1",
        line_type=LineType.COMBINED,
        description="PEX + plumber",
        customer_description="PEX repipe with plumber labor",
        material=material,
        labor=labor,
    )
    estimate = EstimateInput(lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.MATERIALS_ONLY)
    result = calculate(estimate)
    view = to_customer_view(result)

    assert len(view.lines) == 1
    line_view = view.lines[0]
    assert line_view.quantity == "180"
    assert line_view.unit == "LF"
    assert line_view.price_cents == 46359
    assert view.subtotal_cents == 46359
    assert view.discount_cents == 0
    assert view.tax_cents == 1134
    assert view.total_cents == 47493


def test_example_c_view():
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
    view = to_customer_view(result)
    prices = [line.price_cents for line in view.lines]
    assert prices == [97638, 120000]
    assert view.subtotal_cents == 217638
    assert view.discount_cents == 10882
    assert view.tax_cents == 5890
    assert view.total_cents == 212646


def test_fixed_flat_view_shows_stored_qty():
    line = LineInput(
        line_key="B1",
        line_type=LineType.LABOR,
        description="drywall hang",
        customer_description="Drywall hang, flat rate",
        labor=LaborInput(
            rate_type=LaborRateType.FIXED_FLAT,
            labor_qty=Decimal("3"),
            labor_unit="ROOM",
            labor_cost_rate_cents=40000,
            labor_bill_rate_cents=85000,
            labor_type="drywall hang",
        ),
    )
    estimate = EstimateInput(lines=(line,), tax_rate_bp=635, tax_method=TaxMethod.MATERIALS_ONLY)
    result = calculate(estimate)
    view = to_customer_view(result)
    assert view.lines[0].quantity == "3"
    assert view.lines[0].unit == "room"
