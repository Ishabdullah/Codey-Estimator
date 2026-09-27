from decimal import Decimal

import pytest

from codey_estimator.catalog.normalizer import normalize_product
from codey_estimator.catalog.package import (
    PackageSource,
    PackageSpec,
    infer_package,
    validate_package,
)
from codey_estimator.catalog.schema import Category
from codey_estimator.errors import CatalogValidationError

PIPE = Category.PLUMBING_PIPE
DRYWALL = Category.DRYWALL_SHEET
LUMBER = Category.LUMBER
FASTENER = Category.FASTENER
PAINT = Category.PAINT

n1 = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
n6 = normalize_product("SharkBite 1/2 in. Red PEX-B Pipe", PIPE, brand="SharkBite")
n11 = normalize_product("1/2 in. x 10 ft. PEX-A Pipe (5-Pack)", PIPE)
d1 = normalize_product(
    "Sheetrock UltraLight 1/2 in. x 4 ft. x 8 ft. Gypsum Board", DRYWALL, brand="USG"
)
l1 = normalize_product("2 in. x 4 in. x 8 ft. Premium Kiln-Dried Whitewood Stud", LUMBER)
f1 = normalize_product(
    "#8 x 1-5/8 in. Phillips Bugle-Head Coarse Thread Drywall Screws (100-Pack)",
    FASTENER,
    brand="Grip-Rite",
)
f4 = normalize_product("16d x 3-1/2 in. Bright Common Nails (5 lb. Box)", FASTENER)
p1 = normalize_product(
    "BEHR PREMIUM PLUS 1 gal. Ultra Pure White Eggshell Enamel Low Odor Interior Paint & Primer",
    PAINT,
    brand="BEHR",
)
p2 = normalize_product("Glidden 1 qt. White Eggshell Interior Paint", PAINT)
p3 = normalize_product("Behr 5 gal. Semi-Gloss Exterior Paint", PAINT)
p6 = normalize_product("Glidden (2-Pack) 1 qt. White Eggshell Interior Paint", PAINT)


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        (n1, (Decimal("50"), "FT")),
        (n11, (Decimal("50"), "FT")),
        (n6, None),
        (d1, (Decimal("32"), "SF")),
        (l1, (Decimal("1"), "EA")),
        (f1, (Decimal("100"), "EA")),
        (f4, None),
        (p1, (Decimal("1"), "GAL")),
        (p2, (Decimal("1"), "QT")),
        (p3, (Decimal("5"), "GAL")),
        (p6, (Decimal("2"), "QT")),
    ],
)
def test_infer_package(attrs, expected):
    assert infer_package(attrs) == expected


def test_validate_manual_on_retailer_linked_raises():
    spec = PackageSpec(Decimal(50), "FT", PackageSource.MANUAL_ENTRY)
    with pytest.raises(CatalogValidationError) as exc:
        validate_package(spec, retailer_linked=True)
    assert exc.value.code == "MANUAL_PACKAGE_ON_RETAILER_PRODUCT"


def test_validate_manual_unlinked_ok():
    spec = PackageSpec(Decimal(50), "FT", PackageSource.MANUAL_ENTRY)
    assert validate_package(spec, retailer_linked=False) is None


def test_validate_retailer_listing_linked_ok():
    spec = PackageSpec(Decimal(50), "FT", PackageSource.RETAILER_LISTING)
    assert validate_package(spec, retailer_linked=True) is None


def test_validate_qty_below_one_raises():
    spec = PackageSpec(Decimal("0.5"), "FT", PackageSource.RETAILER_LISTING)
    with pytest.raises(CatalogValidationError) as exc:
        validate_package(spec, retailer_linked=False)
    assert exc.value.code == "INVALID_PACKAGE_QTY"


def test_validate_non_finite_raises():
    spec = PackageSpec(Decimal("Infinity"), "FT", PackageSource.RETAILER_LISTING)
    with pytest.raises(CatalogValidationError) as exc:
        validate_package(spec, retailer_linked=False)
    assert exc.value.code == "INVALID_PACKAGE_QTY"


def test_validate_float_or_bool_raises_type_error():
    float_spec = PackageSpec(1.5, "FT", PackageSource.RETAILER_LISTING)
    with pytest.raises(TypeError):
        validate_package(float_spec, retailer_linked=False)
    bool_spec = PackageSpec(True, "FT", PackageSource.RETAILER_LISTING)
    with pytest.raises(TypeError):
        validate_package(bool_spec, retailer_linked=False)


def test_validate_bad_unit_raises():
    spec = PackageSpec(Decimal(50), "ft", PackageSource.RETAILER_LISTING)
    with pytest.raises(CatalogValidationError) as exc:
        validate_package(spec, retailer_linked=False)
    assert exc.value.code == "INVALID_PACKAGE_UNIT"
