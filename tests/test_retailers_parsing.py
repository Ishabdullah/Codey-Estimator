from decimal import Decimal

import pytest

from codey_estimator.errors import RetailerDataError
from codey_estimator.retailers.parsing import (
    CsvDateFormat,
    clean_text,
    days_from_civil,
    parse_date,
    parse_package_cells,
    parse_package_text,
    parse_price_cents,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("$42.97", 4297),
        ("$ 42.97", 4297),
        ("42.9", 4290),
        ("42", 4200),
        ("$1,234.50", 123450),
        (" 8.98 ", 898),
    ],
)
def test_parse_price_cents_table(text, expected):
    assert parse_price_cents(text, field="Price") == expected


@pytest.mark.parametrize(
    "text",
    ["abc", "-3.00", "0.00", "42.975", "1,23.00", "(3.00)"],
)
def test_parse_price_cents_invalid(text):
    with pytest.raises(RetailerDataError) as exc_info:
        parse_price_cents(text, field="Price")
    assert exc_info.value.code == "INVALID_PRICE"
    assert exc_info.value.field == "Price"


def test_parse_price_cents_missing():
    with pytest.raises(RetailerDataError) as exc_info:
        parse_price_cents("", field="Price")
    assert exc_info.value.code == "MISSING_REQUIRED_VALUE"
    assert exc_info.value.field == "Price"


@pytest.mark.parametrize(
    "text,qty,unit",
    [
        ("50 ft", Decimal("50"), "FT"),
        ("50ft", Decimal("50"), "FT"),
        ("50 FT.", Decimal("50"), "FT"),
        ("1 gallon", Decimal(1), "GAL"),
        ("100 each", Decimal(100), "EA"),
        ("32 sq ft", Decimal(32), "SF"),
        ("32 sq  ft", Decimal(32), "SF"),
        ("1,000 pcs", Decimal(1000), "EA"),
        ("ea", Decimal(1), "EA"),
        ("", Decimal(1), None),
    ],
)
def test_parse_package_text_table(text, qty, unit):
    result_qty, result_unit = parse_package_text(text, field="Size")
    assert result_qty == qty
    assert result_unit == unit


@pytest.mark.parametrize(
    "text,code",
    [
        ("50", "PACKAGE_UNIT_MISSING"),
        ("1/2 gal", "INVALID_PACKAGE_QTY"),
        ("0.5 gal", "INVALID_PACKAGE_QTY"),
        ("12 pack", "INVALID_PACKAGE_UNIT"),
        ("fifty ft", "INVALID_PACKAGE_UNIT"),
    ],
)
def test_parse_package_text_errors(text, code):
    with pytest.raises(RetailerDataError) as exc_info:
        parse_package_text(text, field="Size")
    assert exc_info.value.code == code
    assert exc_info.value.field == "Size"


@pytest.mark.parametrize(
    "qty_text,unit_text,qty,unit",
    [
        ("50", "ft", Decimal(50), "FT"),
        ("50.0", "FEET", Decimal(50), "FT"),
        ("", "", Decimal(1), None),
        ("", "ea", Decimal(1), "EA"),
    ],
)
def test_parse_package_cells_table(qty_text, unit_text, qty, unit):
    result_qty, result_unit = parse_package_cells(
        qty_text, unit_text, qty_field="Qty", unit_field="Unit"
    )
    assert result_qty == qty
    assert result_unit == unit


def test_parse_package_cells_unit_missing():
    with pytest.raises(RetailerDataError) as exc_info:
        parse_package_cells("50", "", qty_field="Qty", unit_field="Unit")
    assert exc_info.value.code == "PACKAGE_UNIT_MISSING"
    assert exc_info.value.field == "Unit"


@pytest.mark.parametrize("qty_text", ["fifty", "0", "1e3", "NaN"])
def test_parse_package_cells_invalid_qty(qty_text):
    with pytest.raises(RetailerDataError) as exc_info:
        parse_package_cells(qty_text, "ft", qty_field="Qty", unit_field="Unit")
    assert exc_info.value.code == "INVALID_PACKAGE_QTY"
    assert exc_info.value.field == "Qty"


@pytest.mark.parametrize(
    "args,expected",
    [
        ((1970, 1, 1), 0),
        ((2000, 3, 1), 11017),
        ((2024, 2, 29), 19782),
        ((2026, 9, 14), 20710),
    ],
)
def test_days_from_civil_known_values(args, expected):
    assert days_from_civil(*args) == expected


@pytest.mark.parametrize(
    "text,fmt,offset,expected",
    [
        ("2024-02-29", CsvDateFormat.ISO, 0, 1709164800),
        ("2000-02-29", CsvDateFormat.ISO, 0, 951782400),
        ("9/14/2026", CsvDateFormat.US, -14400, 1789358400),
    ],
)
def test_parse_date_table(text, fmt, offset, expected):
    assert parse_date(text, fmt, offset, field="Date") == expected


@pytest.mark.parametrize(
    "text,fmt,offset",
    [
        ("2026-02-29", CsvDateFormat.ISO, 0),
        ("2026-9-14", CsvDateFormat.ISO, 0),
        ("1900-02-29", CsvDateFormat.ISO, 0),
        ("1969-12-31", CsvDateFormat.ISO, 0),
    ],
)
def test_parse_date_invalid(text, fmt, offset):
    with pytest.raises(RetailerDataError) as exc_info:
        parse_date(text, fmt, offset, field="Date")
    assert exc_info.value.code == "INVALID_DATE"


def test_parse_date_after_import():
    imported_at = 1790510400
    after = parse_date("9/28/2026", CsvDateFormat.US, -14400, field="Date")
    before = parse_date("9/27/2026", CsvDateFormat.US, -14400, field="Date")
    assert after > imported_at
    assert before <= imported_at
    assert after == 1790568000
    assert before == 1790481600


def test_clean_text():
    assert clean_text(None) is None
    assert clean_text("  x ") == "x"
    assert clean_text("   ") is None
    with pytest.raises(TypeError):
        clean_text(5)  # type: ignore[arg-type]
