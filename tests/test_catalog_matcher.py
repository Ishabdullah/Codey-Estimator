from fractions import Fraction as F

import pytest

from codey_estimator.catalog.matcher import (
    MatchCandidate,
    MatchMethod,
    MatchStatus,
    MatchTarget,
    classify,
    match,
    normalize_model_number,
    normalize_upc,
)
from codey_estimator.catalog.normalizer import normalize_product
from codey_estimator.catalog.schema import Attr, Category, Measure, make_attributes
from codey_estimator.errors import CatalogValidationError

PIPE = Category.PLUMBING_PIPE
DRYWALL = Category.DRYWALL_SHEET
LUMBER = Category.LUMBER
FASTENER = Category.FASTENER
PAINT = Category.PAINT


def M(v, u):
    return Measure(F(v), u)


def pipe(**kw):
    return make_attributes(PIPE, kw)


n1 = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
n2 = normalize_product('Apollo ½" x 50\' Red PEX B Tubing', PIPE, brand="Apollo")
n3 = normalize_product("SharkBite 3/4 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
n4 = normalize_product("1/2 in. x 50 ft. PEX-B Pipe", PIPE)
n5 = normalize_product("SharkBite 1/2 in. x 50 ft. Blue PEX-B Pipe", PIPE, brand="SharkBite")
n6 = normalize_product("SharkBite 1/2 in. Red PEX-B Pipe", PIPE, brand="SharkBite")
n7 = normalize_product("Red PEX-B", PIPE)
n8 = normalize_product("SharkBite U870R50 Pipe", PIPE, brand="SharkBite")
n9 = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX Pipe", PIPE, brand="SharkBite")
n10 = normalize_product("SharkBite 1/2 in. x 50 ft. PEX-B Pipe", PIPE, brand="SharkBite")
T_A = pipe(
    **{
        Attr.MATERIAL: "PEX",
        Attr.SUBTYPE: "PEX-A",
        Attr.NOMINAL_SIZE: M("1/2", "IN"),
        Attr.COLOR: "red",
        Attr.LENGTH: M(50, "FT"),
        Attr.PRODUCT_TYPE: "pipe",
    }
)

d1 = normalize_product(
    "Sheetrock UltraLight 1/2 in. x 4 ft. x 8 ft. Gypsum Board", DRYWALL, brand="USG"
)
d2 = normalize_product(
    "Gold Bond 1/2\" x 4' x 8' Mold-Resistant Drywall", DRYWALL, brand="Gold Bond"
)
d3 = normalize_product("5/8 in. x 4 ft. x 8 ft. Type X Drywall", DRYWALL)
d4 = normalize_product("1/2 4x8 drywall", DRYWALL)

l1 = normalize_product("2 in. x 4 in. x 8 ft. Premium Kiln-Dried Whitewood Stud", LUMBER)
l2 = normalize_product(
    "2 in. x 4 in. x 96 in. Pressure-Treated Southern Yellow Pine Lumber", LUMBER
)
l3 = normalize_product("2x4x8 SPF Stud", LUMBER)
l4 = normalize_product("2 in. x 4 in. x 92-5/8 in. Stud", LUMBER)
l9 = normalize_product("2 in. x 4 in. x 8 ft. Pressure-Treated Lumber", LUMBER)

f1 = normalize_product(
    "#8 x 1-5/8 in. Phillips Bugle-Head Coarse Thread Drywall Screws (100-Pack)",
    FASTENER,
    brand="Grip-Rite",
)
f2 = normalize_product("No. 8 x 1-5/8 in. Drywall Screw, Box of 1000", FASTENER)
f3 = normalize_product("#8 x 1-5/8 in. Deck Screws", FASTENER)

p1 = normalize_product(
    "BEHR PREMIUM PLUS 1 gal. Ultra Pure White Eggshell Enamel Low Odor Interior Paint & Primer",
    PAINT,
    brand="BEHR",
)
p2 = normalize_product("Glidden 1 qt. White Eggshell Interior Paint", PAINT)


def test_m1_sharkbite_vs_apollo():
    r = match(MatchTarget(n1), MatchCandidate(n2))
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert set(r.matching) == {
        Attr.MATERIAL,
        Attr.SUBTYPE,
        Attr.NOMINAL_SIZE,
        Attr.COLOR,
        Attr.LENGTH,
        Attr.PRODUCT_TYPE,
    }
    assert r.differing == (Attr.BRAND,)
    assert r.conflicting == ()
    assert r.missing == ()
    assert r.subtype_capped is False


def test_m1r_symmetry():
    r = match(MatchTarget(n2), MatchCandidate(n1))
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED


def test_m2_subtype_mismatch():
    r = match(MatchTarget(T_A), MatchCandidate(n1))
    assert r.confidence_bp == 7000
    assert r.status == MatchStatus.PROPOSED
    assert r.matching == (
        Attr.MATERIAL,
        Attr.NOMINAL_SIZE,
        Attr.COLOR,
        Attr.LENGTH,
        Attr.PRODUCT_TYPE,
    )
    assert r.differing == (Attr.SUBTYPE,)
    assert r.subtype_capped is True


def test_m2b_cap_is_ceiling():
    r = match(MatchTarget(T_A), MatchCandidate(n10))
    assert r.confidence_bp == 6939
    assert r.status == MatchStatus.PROPOSED
    assert r.differing == (Attr.SUBTYPE,)
    assert r.missing == (Attr.COLOR,)
    assert r.subtype_capped is True


def test_m3_conflicting_required():
    r = match(MatchTarget(n1), MatchCandidate(n3))
    assert r.confidence_bp == 0
    assert r.status == MatchStatus.NO_MATCH
    assert r.conflicting == (Attr.NOMINAL_SIZE,)
    assert r.matching == (
        Attr.MATERIAL,
        Attr.SUBTYPE,
        Attr.COLOR,
        Attr.LENGTH,
        Attr.PRODUCT_TYPE,
        Attr.BRAND,
    )
    assert r.subtype_capped is False


def test_m4_color_missing():
    r = match(MatchTarget(n1), MatchCandidate(n4))
    assert r.confidence_bp == 9388
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.missing == (Attr.COLOR,)
    assert Attr.BRAND not in r.matching
    assert Attr.BRAND not in r.differing
    assert Attr.BRAND not in r.missing


def test_m5_color_differs():
    r = match(MatchTarget(n1), MatchCandidate(n5))
    assert r.confidence_bp == 8776
    assert r.status == MatchStatus.PROPOSED
    assert r.differing == (Attr.COLOR,)
    assert Attr.BRAND in r.matching


def test_m6_subtype_unknown():
    r = match(MatchTarget(n1), MatchCandidate(n9))
    assert r.confidence_bp == 8776
    assert r.status == MatchStatus.PROPOSED
    assert r.missing == (Attr.SUBTYPE,)
    assert r.subtype_capped is False


def test_m7_required_missing():
    r = match(MatchTarget(n1), MatchCandidate(n6))
    assert r.confidence_bp == 7959
    assert r.status == MatchStatus.PROPOSED
    assert r.missing == (Attr.LENGTH,)


def test_m8_below_threshold():
    r = match(MatchTarget(n1), MatchCandidate(n7))
    assert r.confidence_bp == 3878
    assert r.status == MatchStatus.NO_MATCH
    assert r.missing == (Attr.NOMINAL_SIZE, Attr.LENGTH, Attr.PRODUCT_TYPE)


def test_m9_upc_exact():
    r = match(
        MatchTarget(n1, known_upcs=frozenset({"689522034567"})),
        MatchCandidate(n8, upc="6-89522-03456-7"),
    )
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.method == MatchMethod.UPC
    assert r.matching == (Attr.PRODUCT_TYPE, Attr.BRAND)
    assert r.missing == (Attr.MATERIAL, Attr.SUBTYPE, Attr.NOMINAL_SIZE, Attr.COLOR, Attr.LENGTH)


def test_m9b_same_pair_no_upc():
    r = match(MatchTarget(n1), MatchCandidate(n8))
    assert r.confidence_bp == 2041
    assert r.status == MatchStatus.NO_MATCH


def test_m10_model_number():
    r = match(
        MatchTarget(n1, known_models=frozenset({("SharkBite", "U870R50")})),
        MatchCandidate(n8, model_number="u870-r50"),
    )
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.method == MatchMethod.MODEL_NUMBER


def test_m10b_model_number_brand_differs():
    n8_apollo = normalize_product("SharkBite U870R50 Pipe", PIPE, brand="Apollo")
    r = match(
        MatchTarget(n1, known_models=frozenset({("SharkBite", "U870R50")})),
        MatchCandidate(n8_apollo, model_number="u870-r50"),
    )
    assert r.confidence_bp == 2041
    assert r.status == MatchStatus.NO_MATCH
    assert r.differing == (Attr.BRAND,)


def test_m11_upc_plus_conflict():
    r = match(
        MatchTarget(n1, known_upcs=frozenset({"689522034567"})),
        MatchCandidate(n3, upc="689522034567"),
    )
    assert r.status == MatchStatus.PROPOSED
    assert r.method == MatchMethod.UPC
    assert r.confidence_bp == 10000
    assert r.conflicting == (Attr.NOMINAL_SIZE,)


def test_m12_upc_plus_subtype_differs():
    r = match(
        MatchTarget(T_A, known_upcs=frozenset({"689522034567"})),
        MatchCandidate(n1, upc="689522034567"),
    )
    assert r.status == MatchStatus.PROPOSED
    assert r.method == MatchMethod.UPC
    assert r.differing == (Attr.SUBTYPE,)
    assert r.subtype_capped is False


def test_md1_drywall_subtype():
    r = match(MatchTarget(d1), MatchCandidate(d2))
    assert r.confidence_bp == 6667
    assert r.status == MatchStatus.PROPOSED
    assert set(r.differing) == {Attr.SUBTYPE, Attr.BRAND}
    assert r.matching == (Attr.THICKNESS, Attr.WIDTH, Attr.LENGTH)
    assert r.subtype_capped is True


def test_md2_drywall_conflict():
    r = match(MatchTarget(d1), MatchCandidate(d3))
    assert r.confidence_bp == 0
    assert r.status == MatchStatus.NO_MATCH
    assert r.conflicting == (Attr.THICKNESS,)
    assert r.differing == (Attr.SUBTYPE,)
    assert r.matching == (Attr.WIDTH, Attr.LENGTH)
    assert r.subtype_capped is False


def test_md3_query_matches_listing():
    r = match(MatchTarget(d1), MatchCandidate(d4))
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.matching == (Attr.SUBTYPE, Attr.THICKNESS, Attr.WIDTH, Attr.LENGTH)


def test_ml1_lumber_treatment_conflict():
    r = match(MatchTarget(l1), MatchCandidate(l2))
    assert r.confidence_bp == 0
    assert r.status == MatchStatus.NO_MATCH
    assert r.conflicting == (Attr.TREATMENT,)
    assert r.matching == (Attr.DIMENSION, Attr.LENGTH)


def test_ml2_material_ignored_when_target_lacks_it():
    r = match(MatchTarget(l1), MatchCandidate(l3))
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.matching == (Attr.DIMENSION, Attr.LENGTH, Attr.TREATMENT)


def test_ml3_optional_missing():
    r = match(MatchTarget(l2), MatchCandidate(l9))
    assert r.confidence_bp == 9091
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.missing == (Attr.MATERIAL,)


def test_ml4_length_conflict():
    r = match(MatchTarget(l1), MatchCandidate(l4))
    assert r.confidence_bp == 0
    assert r.status == MatchStatus.NO_MATCH
    assert r.conflicting == (Attr.LENGTH,)


def test_mf1_package_differs_no_penalty():
    r = match(MatchTarget(f1), MatchCandidate(f2))
    assert r.confidence_bp == 10000
    assert r.status == MatchStatus.AUTO_CONFIRMED
    assert r.matching == (Attr.PRODUCT_TYPE, Attr.SUBTYPE, Attr.GAUGE, Attr.LENGTH)
    assert r.differing == (Attr.PACKAGE_COUNT,)


def test_mf2_fastener_subtype_capped():
    r = match(MatchTarget(f1), MatchCandidate(f3))
    assert r.confidence_bp == 6667
    assert r.status == MatchStatus.PROPOSED
    assert r.differing == (Attr.SUBTYPE,)
    assert r.subtype_capped is True


def test_mp1_paint_volume_conflict():
    r = match(MatchTarget(p1), MatchCandidate(p2))
    assert r.confidence_bp == 0
    assert r.status == MatchStatus.NO_MATCH
    assert r.conflicting == (Attr.VOLUME,)
    assert r.matching == (Attr.PRODUCT_TYPE, Attr.SUBTYPE, Attr.FINISH, Attr.COLOR)


def test_classify_boundaries():
    assert classify(9000, False) == MatchStatus.AUTO_CONFIRMED
    assert classify(8999, False) == MatchStatus.PROPOSED
    assert classify(6000, False) == MatchStatus.PROPOSED
    assert classify(5999, False) == MatchStatus.NO_MATCH
    assert classify(10000, True) == MatchStatus.NO_MATCH
    for bad in (-1, 10001):
        with pytest.raises(ValueError):
            classify(bad, False)
    with pytest.raises(ValueError):
        classify(True, False)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("6-89522-03456-7", "00689522034567"),
        ("0689522034567", "00689522034567"),
        ("12345", None),
        ("68952203456X", None),
        ("", None),
    ],
)
def test_normalize_upc(raw, expected):
    assert normalize_upc(raw) == expected


def test_normalize_model_number():
    assert normalize_model_number("u870-r50") == "U870R50"
    assert normalize_model_number(None) is None
    assert normalize_model_number("---") is None


def test_category_mismatch_raises():
    with pytest.raises(CatalogValidationError) as exc:
        match(MatchTarget(d1), MatchCandidate(n1))
    assert exc.value.code == "CATEGORY_MISMATCH"


def test_incomplete_target_raises():
    nq = normalize_product("1/2 red pex", PIPE)
    with pytest.raises(CatalogValidationError) as exc:
        match(MatchTarget(nq), MatchCandidate(n1))
    assert exc.value.code == "MISSING_REQUIRED_ATTRIBUTE"
    assert exc.value.attr == "length"


def test_match_deterministic():
    a = match(MatchTarget(n1), MatchCandidate(n2))
    b = match(MatchTarget(n1), MatchCandidate(n2))
    assert a == b
