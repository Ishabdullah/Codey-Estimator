from fractions import Fraction as F

import pytest

from codey_estimator.catalog.normalizer import normalize_product
from codey_estimator.catalog.schema import Attr, Category, Measure, make_attributes
from codey_estimator.errors import UnknownCategoryError

PIPE = Category.PLUMBING_PIPE
DRYWALL = Category.DRYWALL_SHEET
LUMBER = Category.LUMBER
FASTENER = Category.FASTENER
PAINT = Category.PAINT


def M(v, u):
    return Measure(F(v), u)


def pipe(**kw):
    return make_attributes(PIPE, kw)


def drywall(**kw):
    return make_attributes(DRYWALL, kw)


def lumber(**kw):
    return make_attributes(LUMBER, kw)


def fastener(**kw):
    return make_attributes(FASTENER, kw)


def paint(**kw):
    return make_attributes(PAINT, kw)


@pytest.mark.parametrize(
    "token",
    [
        "1/2",
        "½",
        "0.5",
        ".5",
        "0.50 in",
        "1/2-in",
        "1/2 in.",
        '1/2"',
        "1/2in",
        "1/2 inch",
    ],
)
def test_fraction_forms_equivalent(token):
    result = normalize_product(f"{token} pex pipe", PIPE)
    assert result.get(Attr.NOMINAL_SIZE) == M("1/2", "IN")


def test_fraction_forms_mixed_vulgar():
    result = normalize_product("1½ in pex", PIPE)
    assert result.get(Attr.NOMINAL_SIZE) == M("3/2", "IN")


@pytest.mark.parametrize(
    "token",
    ["50 ft", "50-ft", "50'", "50 feet", "50ft", "50 ft.", "50′"],
)
def test_length_forms_equivalent(token):
    result = normalize_product(f"1/2 in. x {token} pex pipe", PIPE)
    assert result.get(Attr.LENGTH) == M(50, "FT")


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("10-pack", 10),
        ("10 pack", 10),
        ("10pk", 10),
        ("(25-count)", 25),
        ("50 ct", 50),
        ("box of 100", 100),
        ("pack of 10", 10),
        ("box of 1,000", 1000),
        ("1 lb. box", None),
    ],
)
def test_pack_count_forms(token, expected):
    result = normalize_product(f"#8 x 1-5/8 in. drywall screws {token}", FASTENER)
    assert result.get(Attr.PACKAGE_COUNT) == expected


def test_n1_sharkbite():
    result = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.COLOR: "red",
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "SharkBite",
        }
    )
    assert result == expected


def test_n2_apollo():
    result = normalize_product('Apollo ½" x 50\' Red PEX B Tubing', PIPE, brand="Apollo")
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.COLOR: "red",
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "Apollo",
        }
    )
    assert result == expected


def test_nq_bare_size():
    result = normalize_product("1/2 red pex", PIPE)
    expected = pipe(**{Attr.MATERIAL: "PEX", Attr.NOMINAL_SIZE: M("1/2", "IN"), Attr.COLOR: "red"})
    assert result == expected


def test_n3_different_size():
    result = normalize_product("SharkBite 3/4 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("3/4", "IN"),
            Attr.COLOR: "red",
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "SharkBite",
        }
    )
    assert result == expected


def test_n4_no_brand():
    result = normalize_product("1/2 in. x 50 ft. PEX-B Pipe", PIPE)
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
        }
    )
    assert result == expected


def test_n5_blue():
    result = normalize_product(
        "SharkBite 1/2 in. x 50 ft. Blue PEX-B Pipe", PIPE, brand="SharkBite"
    )
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.COLOR: "blue",
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "SharkBite",
        }
    )
    assert result == expected


def test_n6_no_length():
    result = normalize_product("SharkBite 1/2 in. Red PEX-B Pipe", PIPE, brand="SharkBite")
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.COLOR: "red",
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "SharkBite",
        }
    )
    assert result == expected


def test_n7_minimal():
    result = normalize_product("Red PEX-B", PIPE)
    expected = pipe(**{Attr.MATERIAL: "PEX", Attr.SUBTYPE: "PEX-B", Attr.COLOR: "red"})
    assert result == expected


def test_n8_model_number_not_a_size():
    result = normalize_product("SharkBite U870R50 Pipe", PIPE, brand="SharkBite")
    expected = pipe(**{Attr.PRODUCT_TYPE: "pipe", Attr.BRAND: "SharkBite"})
    assert result == expected


def test_n9_no_subtype():
    result = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX Pipe", PIPE, brand="SharkBite")
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.COLOR: "red",
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "SharkBite",
        }
    )
    assert result == expected


def test_n10_no_color():
    result = normalize_product("SharkBite 1/2 in. x 50 ft. PEX-B Pipe", PIPE, brand="SharkBite")
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-B",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.LENGTH: M(50, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.BRAND: "SharkBite",
        }
    )
    assert result == expected


def test_n11_pack_count():
    result = normalize_product("1/2 in. x 10 ft. PEX-A Pipe (5-Pack)", PIPE)
    expected = pipe(
        **{
            Attr.MATERIAL: "PEX",
            Attr.SUBTYPE: "PEX-A",
            Attr.NOMINAL_SIZE: M("1/2", "IN"),
            Attr.LENGTH: M(10, "FT"),
            Attr.PRODUCT_TYPE: "pipe",
            Attr.PACKAGE_COUNT: 5,
        }
    )
    assert result == expected


def test_d1_sheetrock():
    result = normalize_product(
        "Sheetrock UltraLight 1/2 in. x 4 ft. x 8 ft. Gypsum Board", DRYWALL, brand="USG"
    )
    expected = drywall(
        **{
            Attr.SUBTYPE: "REGULAR",
            Attr.THICKNESS: M("1/2", "IN"),
            Attr.WIDTH: M(4, "FT"),
            Attr.LENGTH: M(8, "FT"),
            Attr.BRAND: "USG",
        }
    )
    assert result == expected


def test_d2_gold_bond_mold_resistant():
    result = normalize_product(
        'Gold Bond 1/2" x 4\' x 8\' Mold-Resistant Drywall', DRYWALL, brand="Gold Bond"
    )
    expected = drywall(
        **{
            Attr.SUBTYPE: "MOLD-RESISTANT",
            Attr.THICKNESS: M("1/2", "IN"),
            Attr.WIDTH: M(4, "FT"),
            Attr.LENGTH: M(8, "FT"),
            Attr.BRAND: "Gold Bond",
        }
    )
    assert result == expected


def test_d3_type_x():
    result = normalize_product("5/8 in. x 4 ft. x 8 ft. Type X Drywall", DRYWALL)
    expected = drywall(
        **{
            Attr.SUBTYPE: "TYPE-X",
            Attr.THICKNESS: M("5/8", "IN"),
            Attr.WIDTH: M(4, "FT"),
            Attr.LENGTH: M(8, "FT"),
        }
    )
    assert result == expected


def test_d4_short_pair_and_bare_size():
    result = normalize_product("1/2 4x8 drywall", DRYWALL)
    expected = drywall(
        **{
            Attr.SUBTYPE: "REGULAR",
            Attr.THICKNESS: M("1/2", "IN"),
            Attr.WIDTH: M(4, "FT"),
            Attr.LENGTH: M(8, "FT"),
        }
    )
    assert result == expected


def test_l1_untreated_default():
    result = normalize_product(
        "2 in. x 4 in. x 8 ft. Premium Kiln-Dried Whitewood Stud", LUMBER
    )
    expected = lumber(
        **{Attr.DIMENSION: "2x4", Attr.LENGTH: M(8, "FT"), Attr.TREATMENT: "UNTREATED"}
    )
    assert result == expected


def test_l2_pt_syp_inches_length():
    result = normalize_product(
        "2 in. x 4 in. x 96 in. Pressure-Treated Southern Yellow Pine Lumber", LUMBER
    )
    expected = lumber(
        **{
            Attr.DIMENSION: "2x4",
            Attr.LENGTH: M(8, "FT"),
            Attr.TREATMENT: "PT",
            Attr.MATERIAL: "SYP",
        }
    )
    assert result == expected


def test_l3_no_unit_short_heuristic():
    result = normalize_product("2x4x8 SPF Stud", LUMBER)
    expected = lumber(
        **{
            Attr.DIMENSION: "2x4",
            Attr.LENGTH: M(8, "FT"),
            Attr.TREATMENT: "UNTREATED",
            Attr.MATERIAL: "SPF",
        }
    )
    assert result == expected


def test_l4_mixed_inches_length():
    result = normalize_product("2 in. x 4 in. x 92-5/8 in. Stud", LUMBER)
    expected = lumber(
        **{Attr.DIMENSION: "2x4", Attr.LENGTH: M(F(247, 32), "FT"), Attr.TREATMENT: "UNTREATED"}
    )
    assert result == expected


def test_l5_no_unit_long_heuristic():
    result = normalize_product("2x4x92-5/8", LUMBER)
    expected = lumber(
        **{Attr.DIMENSION: "2x4", Attr.LENGTH: M(F(247, 32), "FT"), Attr.TREATMENT: "UNTREATED"}
    )
    assert result == expected


def test_l6_pair_then_ft_measure():
    result = normalize_product("1 in. x 6 in. 8 ft. Common Board", LUMBER)
    expected = lumber(
        **{Attr.DIMENSION: "1x6", Attr.LENGTH: M(8, "FT"), Attr.TREATMENT: "UNTREATED"}
    )
    assert result == expected


def test_l7_dimension_sorted():
    result = normalize_product("4x2x8", LUMBER)
    expected = lumber(
        **{Attr.DIMENSION: "2x4", Attr.LENGTH: M(8, "FT"), Attr.TREATMENT: "UNTREATED"}
    )
    assert result == expected


def test_l8_fractional_dimension():
    result = normalize_product("5/4 in. x 6 in. x 12 ft. Pressure Treated Decking", LUMBER)
    expected = lumber(**{Attr.DIMENSION: "1.25x6", Attr.LENGTH: M(12, "FT"), Attr.TREATMENT: "PT"})
    assert result == expected


def test_l9_pt_hyphenated():
    result = normalize_product("2 in. x 4 in. x 8 ft. Pressure-Treated Lumber", LUMBER)
    expected = lumber(**{Attr.DIMENSION: "2x4", Attr.LENGTH: M(8, "FT"), Attr.TREATMENT: "PT"})
    assert result == expected


def test_f1_drywall_screws_with_pack():
    result = normalize_product(
        "#8 x 1-5/8 in. Phillips Bugle-Head Coarse Thread Drywall Screws (100-Pack)",
        FASTENER,
        brand="Grip-Rite",
    )
    expected = fastener(
        **{
            Attr.PRODUCT_TYPE: "screw",
            Attr.SUBTYPE: "DRYWALL",
            Attr.GAUGE: "#8",
            Attr.LENGTH: M(F(13, 8), "IN"),
            Attr.PACKAGE_COUNT: 100,
            Attr.BRAND: "Grip-Rite",
        }
    )
    assert result == expected


def test_f2_no_dot_gauge_box_of():
    result = normalize_product("No. 8 x 1-5/8 in. Drywall Screw, Box of 1000", FASTENER)
    expected = fastener(
        **{
            Attr.PRODUCT_TYPE: "screw",
            Attr.SUBTYPE: "DRYWALL",
            Attr.GAUGE: "#8",
            Attr.LENGTH: M(F(13, 8), "IN"),
            Attr.PACKAGE_COUNT: 1000,
        }
    )
    assert result == expected


def test_f3_deck_screws():
    result = normalize_product("#8 x 1-5/8 in. Deck Screws", FASTENER)
    expected = fastener(
        **{
            Attr.PRODUCT_TYPE: "screw",
            Attr.SUBTYPE: "DECK",
            Attr.GAUGE: "#8",
            Attr.LENGTH: M(F(13, 8), "IN"),
        }
    )
    assert result == expected


def test_f4_penny_d_form_no_pack():
    result = normalize_product("16d x 3-1/2 in. Bright Common Nails (5 lb. Box)", FASTENER)
    expected = fastener(
        **{Attr.PRODUCT_TYPE: "nail", Attr.GAUGE: "16d", Attr.LENGTH: M(F(7, 2), "IN")}
    )
    assert result == expected


def test_f5_penny_word_form():
    result = normalize_product("16-Penny 3-1/2 in. Nails", FASTENER)
    expected = fastener(
        **{Attr.GAUGE: "16d", Attr.PRODUCT_TYPE: "nail", Attr.LENGTH: M(F(7, 2), "IN")}
    )
    assert result == expected


def test_p1_paint_and_primer():
    result = normalize_product(
        "BEHR PREMIUM PLUS 1 gal. Ultra Pure White Eggshell Enamel Low Odor Interior "
        "Paint & Primer",
        PAINT,
        brand="BEHR",
    )
    expected = paint(
        **{
            Attr.PRODUCT_TYPE: "paint",
            Attr.SUBTYPE: "INTERIOR",
            Attr.FINISH: "eggshell",
            Attr.VOLUME: M(1, "GAL"),
            Attr.COLOR: "white",
            Attr.BRAND: "BEHR",
        }
    )
    assert result == expected


def test_p2_quart_volume():
    result = normalize_product("Glidden 1 qt. White Eggshell Interior Paint", PAINT)
    expected = paint(
        **{
            Attr.PRODUCT_TYPE: "paint",
            Attr.SUBTYPE: "INTERIOR",
            Attr.FINISH: "eggshell",
            Attr.VOLUME: M(F(1, 4), "GAL"),
            Attr.COLOR: "white",
        }
    )
    assert result == expected


def test_p3_semi_gloss_not_gloss():
    result = normalize_product("Behr 5 gal. Semi-Gloss Exterior Paint", PAINT)
    expected = paint(
        **{
            Attr.PRODUCT_TYPE: "paint",
            Attr.SUBTYPE: "EXTERIOR",
            Attr.FINISH: "semi-gloss",
            Attr.VOLUME: M(5, "GAL"),
        }
    )
    assert result == expected


def test_p4_interior_exterior_combo():
    result = normalize_product("Valspar Signature Satin Interior/Exterior Paint, Gallon", PAINT)
    expected = paint(
        **{
            Attr.PRODUCT_TYPE: "paint",
            Attr.SUBTYPE: "INTERIOR-EXTERIOR",
            Attr.FINISH: "satin",
            Attr.VOLUME: M(1, "GAL"),
        }
    )
    assert result == expected


def test_p5_primer_only():
    result = normalize_product("Drywall Primer 5 gal.", PAINT)
    expected = paint(**{Attr.PRODUCT_TYPE: "primer", Attr.VOLUME: M(5, "GAL")})
    assert result == expected


def test_p6_two_pack_quarts():
    result = normalize_product("Glidden (2-Pack) 1 qt. White Eggshell Interior Paint", PAINT)
    expected = paint(
        **{
            Attr.PRODUCT_TYPE: "paint",
            Attr.SUBTYPE: "INTERIOR",
            Attr.FINISH: "eggshell",
            Attr.VOLUME: M(F(1, 4), "GAL"),
            Attr.COLOR: "white",
            Attr.PACKAGE_COUNT: 2,
        }
    )
    assert result == expected


@pytest.mark.parametrize(
    ("text", "attr", "expected"),
    [
        ("1/2 in. x 10 ft. CPVC Pipe", Attr.MATERIAL, "CPVC"),
        ("3/4 in. x 10 ft. Type L Copper Pipe", Attr.MATERIAL, "COPPER"),
        ("3/4 in. x 10 ft. Type L Copper Pipe", Attr.SUBTYPE, "TYPE-L"),
        ("2 in. x 10 ft. PVC Sch. 40 Pipe", Attr.MATERIAL, "PVC"),
        ("2 in. x 10 ft. PVC Sch. 40 Pipe", Attr.SUBTYPE, "SCH40"),
        ('1½" x 10\' Sch 80 PVC', Attr.SUBTYPE, "SCH80"),
        ('1½" x 10\' Sch 80 PVC', Attr.MATERIAL, "PVC"),
        ("PEX A", Attr.SUBTYPE, "PEX-A"),
        ("PEX-AL-PEX", Attr.MATERIAL, "PEX"),
        ("grey pex", Attr.COLOR, "gray"),
    ],
)
def test_pipe_materials_and_subtypes(text, attr, expected):
    result = normalize_product(text, PIPE)
    assert result.get(attr) == expected


def test_pex_al_pex_has_no_subtype():
    result = normalize_product("PEX-AL-PEX", PIPE)
    assert result.get(Attr.SUBTYPE) is None


def test_empty_text_applies_only_defaults():
    assert normalize_product("", PIPE).values == ()
    assert normalize_product("", DRYWALL).values == ((Attr.SUBTYPE, "REGULAR"),)
    assert normalize_product("", LUMBER).values == ((Attr.TREATMENT, "UNTREATED"),)


def test_brand_blank_is_absent():
    result = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="   ")
    assert result.get(Attr.BRAND) is None


def test_unknown_category_raises():
    with pytest.raises(UnknownCategoryError):
        normalize_product("anything", "not_a_category")


def test_non_str_text_raises_type_error():
    with pytest.raises(TypeError):
        normalize_product(123, PIPE)


def test_deterministic():
    a = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
    b = normalize_product("SharkBite 1/2 in. x 50 ft. Red PEX-B Pipe", PIPE, brand="SharkBite")
    assert a == b
