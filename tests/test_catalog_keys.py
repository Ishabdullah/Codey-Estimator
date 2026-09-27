from fractions import Fraction as F

import pytest

from codey_estimator.catalog.keys import canonical_key
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


def test_key_n1():
    n1 = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
    assert canonical_key(n1) == "plumbing_pipe:PEX|PEX-B|0.5in|red|50ft|pipe"


def test_key_n4():
    n4 = normalize_product("1/2 in. x 50 ft. PEX-B Pipe", PIPE)
    assert canonical_key(n4) == "plumbing_pipe:PEX|PEX-B|0.5in|*|50ft|pipe"


def test_key_no_subtype_no_color():
    result = normalize_product("1/2 in. x 100 ft. PEX Pipe", PIPE)
    assert canonical_key(result) == "plumbing_pipe:PEX|*|0.5in|*|100ft|pipe"


def test_info_attrs_never_in_key():
    n1 = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
    n2 = normalize_product('Apollo ½" x 50\' Red PEX B Tubing', PIPE, brand="Apollo")
    assert canonical_key(n1) == canonical_key(n2)


def test_missing_required_error_names_attr():
    nq = normalize_product("1/2 red pex", PIPE)
    with pytest.raises(CatalogValidationError) as exc:
        canonical_key(nq)
    assert exc.value.code == "MISSING_REQUIRED_ATTRIBUTE"
    assert exc.value.attr == "length"


def test_key_drywall_regular_default():
    d1 = normalize_product(
        "Sheetrock UltraLight 1/2 in. x 4 ft. x 8 ft. Gypsum Board", DRYWALL, brand="USG"
    )
    d4 = normalize_product("1/2 4x8 drywall", DRYWALL)
    assert canonical_key(d1) == "drywall_sheet:REGULAR|0.5in|4ft|8ft"
    assert canonical_key(d4) == "drywall_sheet:REGULAR|0.5in|4ft|8ft"


def test_key_lumber_untreated_no_material():
    l1 = normalize_product("2 in. x 4 in. x 8 ft. Premium Kiln-Dried Whitewood Stud", LUMBER)
    assert canonical_key(l1) == "lumber:2x4|8ft|UNTREATED|*"


def test_key_lumber_pt_syp():
    l2 = normalize_product(
        "2 in. x 4 in. x 96 in. Pressure-Treated Southern Yellow Pine Lumber", LUMBER
    )
    assert canonical_key(l2) == "lumber:2x4|8ft|PT|SYP"


def test_key_lumber_fractional_length():
    l4 = normalize_product("2 in. x 4 in. x 92-5/8 in. Stud", LUMBER)
    assert canonical_key(l4) == "lumber:2x4|7.71875ft|UNTREATED|*"


def test_key_lumber_from_direct_construction():
    lx = make_attributes(
        LUMBER, {Attr.DIMENSION: "2x4", Attr.LENGTH: M(100, "IN"), Attr.TREATMENT: "UNTREATED"}
    )
    assert canonical_key(lx) == "lumber:2x4|25/3ft|UNTREATED|*"


def test_key_fastener_drywall_screw():
    f1 = normalize_product(
        "#8 x 1-5/8 in. Phillips Bugle-Head Coarse Thread Drywall Screws (100-Pack)",
        FASTENER,
        brand="Grip-Rite",
    )
    assert canonical_key(f1) == "fastener:screw|DRYWALL|#8|1.625in|*"


def test_key_fastener_nail_no_subtype():
    f4 = normalize_product("16d x 3-1/2 in. Bright Common Nails (5 lb. Box)", FASTENER)
    assert canonical_key(f4) == "fastener:nail|*|16d|3.5in|*"


def test_key_paint_p1():
    p1 = normalize_product(
        "BEHR PREMIUM PLUS 1 gal. Ultra Pure White Eggshell Enamel Low Odor Interior "
        "Paint & Primer",
        PAINT,
        brand="BEHR",
    )
    assert canonical_key(p1) == "paint:paint|INTERIOR|eggshell|1gal|white"


def test_key_paint_p2():
    p2 = normalize_product("Glidden 1 qt. White Eggshell Interior Paint", PAINT)
    assert canonical_key(p2) == "paint:paint|INTERIOR|eggshell|0.25gal|white"
