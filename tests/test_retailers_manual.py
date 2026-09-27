from decimal import Decimal

import pytest

from codey_estimator.errors import RetailerDataError
from codey_estimator.ports import ObservationSource, PriceObservationData, RetailerProductData
from codey_estimator.retailers.base import ObservedPrice, RetailerOffer
from codey_estimator.retailers.manual import MANUAL_RETAILER_CODE, ManualAdapter, ManualEntry

OBSERVED_AT = 1789918200


def test_manual_entry_end_to_end():
    entry = ManualEntry(
        title="  Red PEX-B pipe 1/2 in x 50 ft  ",
        price_cents=4297,
        package_qty=Decimal("50"),
        package_unit="feet",
        brand="  SharkBite ",
        observed_by_user_id=3,
    )
    offer = ManualAdapter().enter(entry, observed_at=OBSERVED_AT)

    expected_product = RetailerProductData(
        retailer_code="manual",
        retailer_sku="m-e2f3ec930fb01c66",
        title="Red PEX-B pipe 1/2 in x 50 ft",
        brand="SharkBite",
        package_qty=Decimal("50"),
        package_unit="FT",
    )
    expected_price = ObservedPrice(
        price_cents=4297,
        observed_at=OBSERVED_AT,
        source=ObservationSource.MANUAL,
        observed_by_user_id=3,
    )
    assert offer == RetailerOffer(product=expected_product, price=expected_price)
    assert offer.price.bind(41) == PriceObservationData(
        retailer_product_id=41,
        price_cents=4297,
        observed_at=OBSERVED_AT,
        source=ObservationSource.MANUAL,
        observed_by_user_id=3,
    )


def test_manual_sku_stable_across_case_space_and_decimal_scale():
    entry = ManualEntry(
        title="RED  pex-b Pipe 1/2 in x 50 ft",
        price_cents=4499,
        package_qty=Decimal("50.0"),
        package_unit="FT",
    )
    offer = ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    assert offer.product.retailer_sku == "m-e2f3ec930fb01c66"
    assert offer.product.title == "RED  pex-b Pipe 1/2 in x 50 ft"


def test_manual_int_package_qty_and_alias_unit():
    entry = ManualEntry(
        title="Behr Premium Plus Interior Eggshell White 1 gal",
        price_cents=3498,
        package_qty=1,
        package_unit="gallon",
    )
    offer = ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    assert offer.product.package_qty == Decimal(1)
    assert isinstance(offer.product.package_qty, Decimal)
    assert offer.product.package_unit == "GAL"
    assert offer.product.retailer_sku == "m-69694e1691ac9e50"


def test_manual_explicit_sku_stripped():
    entry = ManualEntry(
        title="A pipe",
        price_cents=100,
        package_qty=Decimal(1),
        package_unit="ft",
        retailer_sku=" SKU-1 ",
    )
    offer = ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    assert offer.product.retailer_sku == "SKU-1"


BASE_KWARGS = dict(
    title="A pipe",
    price_cents=100,
    package_qty=Decimal(1),
    package_unit="ft",
)


@pytest.mark.parametrize(
    "overrides,exc_type,code,field",
    [
        ({"package_qty": Decimal("0.5")}, RetailerDataError, "INVALID_PACKAGE_QTY", "package_qty"),
        ({"package_qty": Decimal("NaN")}, RetailerDataError, "INVALID_PACKAGE_QTY", "package_qty"),
        ({"package_unit": "pack"}, RetailerDataError, "INVALID_PACKAGE_UNIT", "package_unit"),
        ({"price_cents": 0}, RetailerDataError, "INVALID_PRICE", "price_cents"),
        ({"price_cents": -1}, RetailerDataError, "INVALID_PRICE", "price_cents"),
        ({"price_cents": 42.97}, TypeError, None, None),
        ({"price_cents": True}, TypeError, None, None),
        ({"package_qty": 50.0}, TypeError, None, None),
        ({"title": "   "}, RetailerDataError, "MISSING_REQUIRED_VALUE", "title"),
        ({"retailer_sku": "  "}, RetailerDataError, "MISSING_REQUIRED_VALUE", "retailer_sku"),
    ],
)
def test_manual_errors(overrides, exc_type, code, field):
    kwargs = {**BASE_KWARGS, **overrides}
    entry = ManualEntry(**kwargs)
    with pytest.raises(exc_type) as exc_info:
        ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    if code is not None:
        assert exc_info.value.code == code
        assert exc_info.value.field == field


def test_manual_observed_at_error():
    entry = ManualEntry(**BASE_KWARGS)
    with pytest.raises(RetailerDataError) as exc_info:
        ManualAdapter().enter(entry, observed_at=-1)
    assert exc_info.value.code == "INVALID_OBSERVED_AT"


def test_manual_observed_by_user_id_error():
    entry = ManualEntry(**BASE_KWARGS, observed_by_user_id=0)
    with pytest.raises(RetailerDataError) as exc_info:
        ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    assert exc_info.value.code == "INVALID_USER_ID"


def test_manual_retailer_code_and_source():
    adapter = ManualAdapter()
    assert adapter.retailer_code == "manual"
    assert adapter.retailer_code == MANUAL_RETAILER_CODE
    assert adapter.source == ObservationSource.MANUAL


def test_manual_deterministic():
    entry = ManualEntry(**BASE_KWARGS)
    offer1 = ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    offer2 = ManualAdapter().enter(entry, observed_at=OBSERVED_AT)
    assert offer1 == offer2
