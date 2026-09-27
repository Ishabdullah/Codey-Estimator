from decimal import Decimal

import pytest

from codey_estimator.errors import CsvImportError, RetailerDataError
from codey_estimator.ports import RetailerProductData
from codey_estimator.retailers.csv_import import CsvColumnMapping, CsvImportAdapter
from codey_estimator.retailers.parsing import CsvDateFormat

CSV_A = (
    "﻿Date,Store,SKU,Description,Brand,UPC,Unit Price,Pkg Qty,Pkg Unit,Qty Purchased\r\n"
    "09/14/2026,6203,1001234567,SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe,SharkBite,"
    "012345678905,$42.97,50,ft,2\r\n"
    '09/14/2026,6203,202345678,"USG Sheetrock 1/2 in. x 4 ft. x 8 ft. Drywall, Regular",'
    "USG,,14.28,32,sq ft,10\r\n"
    "09/15/2026,6203,1001234567,SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe,SharkBite,"
    "012345678905,44.50,50,ft,1\r\n"
    "09/14/2026,6203,1001234567,SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe,SharkBite,"
    "012345678905,$42.97,50,ft,2\r\n"
    "09/14/2026,6203,,Mystery item,Acme,,5.00,1,ea,1\r\n"
    "09/14/2026,6203,300111222,Behr Interior Eggshell 1 gal,Behr,,abc,1,gal,1\r\n"
    "13/45/2026,6203,300111333,Behr Interior Flat 1 gal,Behr,,31.98,1,gal,1\r\n"
    "09/14/2026,6203,1001234567,SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe,SharkBite,"
    "012345678905,79.00,100,ft,1\r\n"
    "09/16/2026,6203,400555666,Grip-Rite #8 x 1-5/8 in. Drywall Screws (1 lb),"
    "Grip-Rite,,8.98,,,1\r\n"
    "\r\n"
    "09/16/2026,6203,500777888,Returned fitting,Apollo,,-3.00,1,ea,-1\r\n"
    "09/16/2026,6203,600999000\r\n"
    '09/16/2026,6203,700111222,"Gorilla 1,000 ct. #6 x 1 in. screws",Gorilla,,'
    '"$1,234.50","1,000",each,1\r\n'
)

CSV_A_MAPPING = CsvColumnMapping(
    sku_column="SKU",
    title_column="Description",
    price_column="Unit Price",
    upc_column="UPC",
    brand_column="Brand",
    store_column="Store",
    date_column="Date",
    package_qty_column="Pkg Qty",
    package_unit_column="Pkg Unit",
    date_format=CsvDateFormat.US,
    utc_offset_seconds=-14400,
)

IMPORTED_AT = 1790510400


def _adapter():
    return CsvImportAdapter("csv:homedepot", CSV_A_MAPPING)


def test_csv_a_full_result():
    result = _adapter().import_text(CSV_A, imported_at=IMPORTED_AT, imported_by_user_id=7)

    assert result.data_rows == 12
    assert result.data_rows == (
        len(result.observations) + len(result.errors) + len(result.duplicate_rows)
    )
    assert result.duplicate_rows == (5,)

    error_summary = [(e.row_number, e.code, e.column) for e in result.errors]
    assert error_summary == [
        (6, "MISSING_REQUIRED_VALUE", "SKU"),
        (7, "INVALID_PRICE", "Unit Price"),
        (8, "INVALID_DATE", "Date"),
        (9, "CONFLICTING_PACKAGE", "Pkg Qty"),
        (12, "INVALID_PRICE", "Unit Price"),
        (13, "ROW_LENGTH_MISMATCH", None),
    ]

    p1 = RetailerProductData(
        retailer_code="csv:homedepot",
        retailer_sku="1001234567",
        title="SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe",
        upc="012345678905",
        brand="SharkBite",
        package_qty=Decimal("50"),
        package_unit="FT",
    )
    p2 = RetailerProductData(
        retailer_code="csv:homedepot",
        retailer_sku="202345678",
        title="USG Sheetrock 1/2 in. x 4 ft. x 8 ft. Drywall, Regular",
        upc=None,
        brand="USG",
        package_qty=Decimal("32"),
        package_unit="SF",
    )
    p3 = RetailerProductData(
        retailer_code="csv:homedepot",
        retailer_sku="400555666",
        title="Grip-Rite #8 x 1-5/8 in. Drywall Screws (1 lb)",
        brand="Grip-Rite",
        package_qty=Decimal(1),
        package_unit=None,
    )
    p4 = RetailerProductData(
        retailer_code="csv:homedepot",
        retailer_sku="700111222",
        title="Gorilla 1,000 ct. #6 x 1 in. screws",
        brand="Gorilla",
        package_qty=Decimal("1000"),
        package_unit="EA",
    )
    assert result.products == (p1, p2, p3, p4)

    obs_summary = [
        (o.row_number, o.retailer_sku, o.price.price_cents, o.price.observed_at)
        for o in result.observations
    ]
    assert obs_summary == [
        (2, "1001234567", 4297, 1789358400),
        (3, "202345678", 1428, 1789358400),
        (4, "1001234567", 4450, 1789444800),
        (10, "400555666", 898, 1789531200),
        (14, "700111222", 123450, 1789531200),
    ]

    expected_hashes = [
        "b41d5131cba3fe502db586ed082066a4cdfdf7c27d69ae547ab545d70581d1df",
        "f7c1decfb89778afd016323699fdefc542a44fd7f1f6fd07de1a9c0d38c1037d",
        "918c858b33cfed2651e2f8ff4937f250fe98f25b3aae4f7cc3e42cd1ca6def61",
        "ff9e6372275d664a07087fdb7cd2d66f154a42c071c8b4f680241a91424a8d17",
        "3d9bf78446c7af9cd230bd08d3a34499b27af18b820a7f2b9bebb36ab1e4894c",
    ]
    actual_hashes = [o.price.raw_hash for o in result.observations]
    assert actual_hashes == expected_hashes, (
        "raw_hash values must match sha256 of the joined raw row cells; "
        "if this fails, trust the implementation's output over the spec's hex digits"
    )

    for o in result.observations:
        assert o.price.store_code == "6203"
        assert o.price.observed_by_user_id == 7
        assert o.price.was_price_cents is None
        assert o.price.unit_price_cents is None
        assert o.price.availability is None


def test_duplicate_formatting_and_store_fallback():
    mapping = CsvColumnMapping(
        sku_column="SKU",
        title_column="Title",
        price_column="Price",
        store_column="Store",
        default_store_code="6203",
    )
    adapter = CsvImportAdapter("csv:dup", mapping)
    text = (
        "SKU,Title,Price,Store\r\n"
        "A1,Pipe,$42.97,6203\r\n"
        "A1,Pipe,42.97,\r\n"
        "A1,Pipe,42.97,6210\r\n"
        "A1,Pipe fitting title changed,43.10,6203\r\n"
    )
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.duplicate_rows == (3,)
    assert [o.price.store_code for o in result.observations] == ["6203", "6210", "6203"]
    assert len(result.products) == 1
    assert result.products[0].title == "Pipe"


def test_missing_columns_listed_in_field_order():
    text = "Date,Store,Item Number,Description,Price\r\n"
    with pytest.raises(CsvImportError) as exc_info:
        _adapter().import_text(text, imported_at=IMPORTED_AT)
    assert exc_info.value.code == "MISSING_COLUMN"
    assert exc_info.value.columns == (
        "SKU",
        "Unit Price",
        "UPC",
        "Brand",
        "Pkg Qty",
        "Pkg Unit",
    )


def test_header_match_case_insensitive():
    mapping = CsvColumnMapping(
        sku_column="SKU", title_column="Description", price_column="Unit Price"
    )
    adapter = CsvImportAdapter("csv:ci", mapping)
    text = "sku,DESCRIPTION,unit price\r\nA1,Widget,1.00\r\n"
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.products[0].retailer_sku == "A1"
    assert result.products[0].title == "Widget"


def test_ambiguous_mapped_column():
    mapping = CsvColumnMapping(
        sku_column="SKU", title_column="Description", price_column="Unit Price"
    )
    adapter = CsvImportAdapter("csv:amb", mapping)
    text = "SKU,Description,sku,Unit Price\r\n"
    with pytest.raises(CsvImportError) as exc_info:
        adapter.import_text(text, imported_at=IMPORTED_AT)
    assert exc_info.value.code == "AMBIGUOUS_COLUMN"
    assert exc_info.value.columns == ("SKU",)


def test_unmapped_duplicate_header_ok():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:notes", mapping)
    text = "SKU,Title,Price,Notes,Notes\r\nA1,Widget,1.00,x,y\r\n"
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.products[0].retailer_sku == "A1"


def test_empty_inputs():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:empty", mapping)
    for text in ("", "﻿", "\r\n\r\n"):
        with pytest.raises(CsvImportError) as exc_info:
            adapter.import_text(text, imported_at=IMPORTED_AT)
        assert exc_info.value.code == "EMPTY_FILE"

    result = adapter.import_text("SKU,Title,Price\r\n", imported_at=IMPORTED_AT)
    assert result.data_rows == 0
    assert result.products == ()
    assert result.observations == ()
    assert result.errors == ()
    assert result.duplicate_rows == ()


def test_malformed_csv_fail_fast():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:bad", mapping)

    unterminated = (
        "SKU,Title,Price\r\n"
        "A1,Pipe,1.00\r\n"
        'A2,"unterminated,2.00\r\n'
        "A3,X,3.00\r\n"
    )
    with pytest.raises(CsvImportError) as exc_info:
        adapter.import_text(unterminated, imported_at=IMPORTED_AT)
    assert exc_info.value.code == "MALFORMED_CSV"
    assert exc_info.value.row_number == 3

    bad_quote = 'SKU,Title,Price\r\nA1,Pipe,1.00\r\na,"ab"c,2.00\r\nA3,X,3.00\r\n'
    with pytest.raises(CsvImportError) as exc_info:
        adapter.import_text(bad_quote, imported_at=IMPORTED_AT)
    assert exc_info.value.code == "MALFORMED_CSV"
    assert exc_info.value.row_number == 3


def test_embedded_newline_and_u2028_in_quoted_title():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:nl", mapping)
    title = "Line1\nLine2 End"
    text = f'SKU,Title,Price\r\nA1,"{title}",1.00\r\nA2,Next,2.00\r\n'
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.products[0].title == title
    assert [o.row_number for o in result.observations] == [2, 3]


def test_trailing_empty_extra_cells_tolerated():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:extra", mapping)

    ok_text = "SKU,Title,Price\r\nA1,Pipe,1.00,\r\n"
    result = adapter.import_text(ok_text, imported_at=IMPORTED_AT)
    assert result.errors == ()
    assert len(result.observations) == 1

    bad_text = "SKU,Title,Price\r\nA1,Pipe,1.00,extra\r\n"
    result = adapter.import_text(bad_text, imported_at=IMPORTED_AT)
    assert len(result.errors) == 1
    assert result.errors[0].code == "ROW_LENGTH_MISMATCH"
    assert result.errors[0].column is None


def test_no_date_column_uses_imported_at():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:nodate", mapping)
    text = "SKU,Title,Price\r\nA1,Pipe,1.00\r\n"
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.observations[0].price.observed_at == IMPORTED_AT


def test_date_after_import():
    text = CSV_A.replace("09/14/2026,6203,1001234567", "09/28/2026,6203,1001234567", 1)
    result = _adapter().import_text(text, imported_at=IMPORTED_AT, imported_by_user_id=7)
    row2_errors = [e for e in result.errors if e.row_number == 2]
    assert len(row2_errors) == 1
    assert row2_errors[0].code == "DATE_AFTER_IMPORT"
    assert row2_errors[0].column == "Date"


def test_combined_package_column():
    mapping = CsvColumnMapping(
        sku_column="SKU", title_column="Title", price_column="Price", package_column="Size"
    )
    adapter = CsvImportAdapter("csv:combined", mapping)
    text = "SKU,Title,Price,Size\r\nA1,Pipe,1.00,50 ft\r\nA2,Other,2.00,50\r\n"
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert len(result.observations) == 1
    assert result.products[0].package_qty == Decimal("50")
    assert result.products[0].package_unit == "FT"
    assert len(result.errors) == 1
    assert result.errors[0].code == "PACKAGE_UNIT_MISSING"
    assert result.errors[0].column == "Size"


def test_tab_delimiter():
    mapping = CsvColumnMapping(
        sku_column="SKU", title_column="Title", price_column="Price", delimiter="\t"
    )
    adapter = CsvImportAdapter("csv:tab", mapping)
    text = "SKU\tTitle\tPrice\r\nA1\tPipe\t1.00\r\n"
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.products[0].retailer_sku == "A1"
    assert result.products[0].title == "Pipe"


@pytest.mark.parametrize(
    "kwargs,exc_type",
    [
        ({"sku_column": 5}, TypeError),
        ({"sku_column": "  "}, CsvImportError),
        ({"package_column": "Size", "package_qty_column": "Qty"}, CsvImportError),
        ({"package_qty_column": "Qty"}, CsvImportError),
        ({"date_format": "iso"}, TypeError),
        ({"utc_offset_seconds": 1.5}, TypeError),
        ({"utc_offset_seconds": 86401}, CsvImportError),
        ({"delimiter": ""}, CsvImportError),
        ({"delimiter": ","}, None),
        ({"delimiter": '"'}, CsvImportError),
        ({"default_store_code": "  "}, CsvImportError),
    ],
)
def test_mapping_validation(kwargs, exc_type):
    base = dict(sku_column="SKU", title_column="Title", price_column="Price")
    base.update(kwargs)
    if exc_type is None:
        CsvColumnMapping(**base)
    else:
        with pytest.raises(exc_type):
            CsvColumnMapping(**base)


def test_retailer_code_validation():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    for bad_code in ("manual", "", "Home Depot", "-x"):
        with pytest.raises(RetailerDataError) as exc_info:
            CsvImportAdapter(bad_code, mapping)
        assert exc_info.value.code == "INVALID_RETAILER_CODE"

    CsvImportAdapter("csv:homedepot", mapping)
    CsvImportAdapter("csv:lowes", mapping)


def test_import_text_arg_validation():
    adapter = _adapter()
    with pytest.raises(TypeError):
        adapter.import_text(b"bytes", imported_at=IMPORTED_AT)
    with pytest.raises(TypeError):
        adapter.import_text("text", imported_at=1.5)
    with pytest.raises(RetailerDataError) as exc_info:
        adapter.import_text("SKU,Title,Price\r\n", imported_at=-1)
    assert exc_info.value.code == "INVALID_OBSERVED_AT"
    with pytest.raises(RetailerDataError) as exc_info:
        adapter.import_text("SKU,Title,Price\r\n", imported_at=0, imported_by_user_id=0)
    assert exc_info.value.code == "INVALID_USER_ID"


def test_import_deterministic():
    result1 = _adapter().import_text(CSV_A, imported_at=IMPORTED_AT, imported_by_user_id=7)
    result2 = _adapter().import_text(CSV_A, imported_at=IMPORTED_AT, imported_by_user_id=7)
    assert result1 == result2


def test_error_rows_register_no_product():
    mapping = CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price")
    adapter = CsvImportAdapter("csv:err", mapping)
    text = "SKU,Title,Price\r\nA1,Pipe,abc\r\n"
    result = adapter.import_text(text, imported_at=IMPORTED_AT)
    assert result.products == ()
    assert len(result.errors) == 1
