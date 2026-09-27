from fractions import Fraction

import pytest

from codey_estimator.catalog.schema import (
    CATEGORY_SCHEMAS,
    Attr,
    AttrKind,
    AttrRole,
    Category,
    Measure,
    NormalizedAttributes,
    get_schema,
    make_attributes,
    normalize_brand,
)
from codey_estimator.errors import (
    CatalogValidationError,
    IncompatibleUnitsError,
    UnknownCategoryError,
    UnknownUnitError,
)

EXPECTED_TABLE = {
    Category.PLUMBING_PIPE: [
        (Attr.MATERIAL, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.SUBTYPE, AttrKind.TEXT, AttrRole.OPTIONAL, 6, None, None),
        (Attr.NOMINAL_SIZE, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "IN", None),
        (Attr.COLOR, AttrKind.TEXT, AttrRole.OPTIONAL, 3, None, None),
        (Attr.LENGTH, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "FT", None),
        (Attr.PRODUCT_TYPE, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.PACKAGE_COUNT, AttrKind.COUNT, AttrRole.INFO, 0, None, None),
        (Attr.BRAND, AttrKind.TEXT, AttrRole.INFO, 0, None, None),
    ],
    Category.DRYWALL_SHEET: [
        (Attr.SUBTYPE, AttrKind.TEXT, AttrRole.OPTIONAL, 6, None, "REGULAR"),
        (Attr.THICKNESS, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "IN", None),
        (Attr.WIDTH, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "FT", None),
        (Attr.LENGTH, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "FT", None),
        (Attr.PACKAGE_COUNT, AttrKind.COUNT, AttrRole.INFO, 0, None, None),
        (Attr.BRAND, AttrKind.TEXT, AttrRole.INFO, 0, None, None),
    ],
    Category.LUMBER: [
        (Attr.DIMENSION, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.LENGTH, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "FT", None),
        (Attr.TREATMENT, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, "UNTREATED"),
        (Attr.MATERIAL, AttrKind.TEXT, AttrRole.OPTIONAL, 3, None, None),
        (Attr.PACKAGE_COUNT, AttrKind.COUNT, AttrRole.INFO, 0, None, None),
        (Attr.BRAND, AttrKind.TEXT, AttrRole.INFO, 0, None, None),
    ],
    Category.FASTENER: [
        (Attr.PRODUCT_TYPE, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.SUBTYPE, AttrKind.TEXT, AttrRole.OPTIONAL, 6, None, None),
        (Attr.GAUGE, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.LENGTH, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "IN", None),
        (Attr.MATERIAL, AttrKind.TEXT, AttrRole.OPTIONAL, 3, None, None),
        (Attr.PACKAGE_COUNT, AttrKind.COUNT, AttrRole.INFO, 0, None, None),
        (Attr.BRAND, AttrKind.TEXT, AttrRole.INFO, 0, None, None),
    ],
    Category.PAINT: [
        (Attr.PRODUCT_TYPE, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.SUBTYPE, AttrKind.TEXT, AttrRole.OPTIONAL, 6, None, None),
        (Attr.FINISH, AttrKind.TEXT, AttrRole.REQUIRED, 10, None, None),
        (Attr.VOLUME, AttrKind.MEASURE, AttrRole.REQUIRED, 10, "GAL", None),
        (Attr.COLOR, AttrKind.TEXT, AttrRole.OPTIONAL, 3, None, None),
        (Attr.PACKAGE_COUNT, AttrKind.COUNT, AttrRole.INFO, 0, None, None),
        (Attr.BRAND, AttrKind.TEXT, AttrRole.INFO, 0, None, None),
    ],
}


def test_every_category_has_schema():
    for category in Category:
        assert category in CATEGORY_SCHEMAS
        assert CATEGORY_SCHEMAS[category].category == category


def test_schema_invariants():
    for schema in CATEGORY_SCHEMAS.values():
        assert len(schema.required) >= 1
        for spec in schema.specs:
            if spec.role is AttrRole.INFO:
                assert spec.weight == 0
            else:
                assert spec.weight > 0
            if spec.kind is AttrKind.MEASURE:
                assert spec.unit is not None
            else:
                assert spec.unit is None
            if spec.default is not None:
                assert spec.kind is AttrKind.TEXT


def test_schema_table_exact():
    for category, rows in EXPECTED_TABLE.items():
        schema = CATEGORY_SCHEMAS[category]
        assert len(schema.specs) == len(rows)
        for spec, (attr, kind, role, weight, unit, default) in zip(
            schema.specs, rows, strict=True
        ):
            assert spec.attr == attr
            assert spec.kind == kind
            assert spec.role == role
            assert spec.weight == weight
            assert spec.unit == unit
            assert spec.default == default


def test_get_schema_accepts_str_and_enum():
    assert get_schema(Category.PLUMBING_PIPE) is CATEGORY_SCHEMAS[Category.PLUMBING_PIPE]
    assert get_schema("plumbing_pipe") is CATEGORY_SCHEMAS[Category.PLUMBING_PIPE]


def test_get_schema_unknown_raises():
    with pytest.raises(UnknownCategoryError):
        get_schema("not_a_category")


def test_make_attributes_orders_and_canonicalizes():
    attrs = make_attributes(
        Category.PLUMBING_PIPE,
        {
            Attr.PRODUCT_TYPE: "pipe",
            Attr.MATERIAL: "pex",
            Attr.COLOR: "Red",
            Attr.LENGTH: Measure(Fraction(50), "FT"),
            Attr.NOMINAL_SIZE: Measure(Fraction(1, 2), "IN"),
            Attr.BRAND: "Shark-Bite",
        },
    )
    assert [a for a, _ in attrs.values] == [
        Attr.MATERIAL,
        Attr.NOMINAL_SIZE,
        Attr.COLOR,
        Attr.LENGTH,
        Attr.PRODUCT_TYPE,
        Attr.BRAND,
    ]
    assert attrs.get(Attr.MATERIAL) == "PEX"
    assert attrs.get(Attr.COLOR) == "red"
    assert attrs.get(Attr.BRAND) == "SHARKBITE"


def test_make_attributes_converts_units():
    attrs = make_attributes(
        Category.PLUMBING_PIPE,
        {
            Attr.MATERIAL: "pex",
            Attr.NOMINAL_SIZE: Measure(Fraction(1, 2), "IN"),
            Attr.LENGTH: Measure(Fraction(600), "IN"),
            Attr.PRODUCT_TYPE: "pipe",
        },
    )
    assert attrs.get(Attr.LENGTH) == Measure(Fraction(50), "FT")

    paint_attrs = make_attributes(
        Category.PAINT,
        {
            Attr.PRODUCT_TYPE: "paint",
            Attr.FINISH: "eggshell",
            Attr.VOLUME: Measure(Fraction(1), "QT"),
        },
    )
    assert paint_attrs.get(Attr.VOLUME) == Measure(Fraction(1, 4), "GAL")


def test_make_attributes_rejects():
    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.GAUGE: "#8"})
    assert exc.value.code == "ATTR_NOT_IN_SCHEMA"

    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.MATERIAL: "  "})
    assert exc.value.code == "INVALID_ATTRIBUTE_VALUE"

    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.MATERIAL: "a|b"})
    assert exc.value.code == "INVALID_ATTRIBUTE_VALUE"

    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.PACKAGE_COUNT: 0})
    assert exc.value.code == "INVALID_ATTRIBUTE_VALUE"

    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.PACKAGE_COUNT: True})
    assert exc.value.code == "INVALID_ATTRIBUTE_VALUE"

    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.MATERIAL: 5})
    assert exc.value.code == "INVALID_ATTRIBUTE_VALUE"

    with pytest.raises(IncompatibleUnitsError):
        make_attributes(Category.PLUMBING_PIPE, {Attr.LENGTH: Measure(Fraction(1), "GAL")})

    with pytest.raises(CatalogValidationError) as exc:
        make_attributes(Category.PLUMBING_PIPE, {Attr.BRAND: "---"})
    assert exc.value.code == "INVALID_ATTRIBUTE_VALUE"


def test_measure_validation():
    with pytest.raises(CatalogValidationError) as exc:
        Measure(Fraction(0), "IN")
    assert exc.value.code == "INVALID_MEASURE"

    with pytest.raises(TypeError):
        Measure(0.5, "IN")

    with pytest.raises(UnknownUnitError):
        Measure(Fraction(1), "FURLONG")


def test_direct_construction_validates():
    with pytest.raises(CatalogValidationError) as exc:
        NormalizedAttributes(
            Category.PLUMBING_PIPE,
            (
                (Attr.NOMINAL_SIZE, Measure(Fraction(1, 2), "IN")),
                (Attr.MATERIAL, "PEX"),
            ),
        )
    assert exc.value.code == "ATTRIBUTE_ORDER"

    with pytest.raises(CatalogValidationError) as exc:
        NormalizedAttributes(
            Category.PLUMBING_PIPE,
            (
                (Attr.MATERIAL, "PEX"),
                (Attr.MATERIAL, "PVC"),
            ),
        )
    assert exc.value.code == "DUPLICATE_ATTRIBUTE"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SharkBite", "SHARKBITE"),
        ("Grip-Rite", "GRIPRITE"),
        ("Gold Bond", "GOLDBOND"),
        ("  ", None),
    ],
)
def test_normalize_brand(raw, expected):
    assert normalize_brand(raw) == expected
