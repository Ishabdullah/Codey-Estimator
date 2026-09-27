import pytest

from codey_estimator.errors import PricingPolicyError
from codey_estimator.refresh import (
    RefreshClass,
    RefreshPolicy,
    RefreshPolicyConfig,
    RefreshStatus,
    RefreshSubject,
    is_search_cache_fresh,
)

L = 1_760_000_000
D = 86_400


def subject(**kwargs: object) -> RefreshSubject:
    defaults: dict[str, object] = {
        "category_key": None,
        "package_price_cents": None,
        "uses_in_window": 0,
        "last_checked_at": L,
        "next_refresh_at": None,
        "refresh_status": RefreshStatus.OK,
        "override_interval_days": None,
    }
    defaults.update(kwargs)
    return RefreshSubject(**defaults)  # type: ignore[arg-type]


def test_config_defaults() -> None:
    cfg = RefreshPolicyConfig()
    assert cfg.normal_interval_days == 180
    assert cfg.frequent_interval_days == 90
    assert cfg.frequent_min_uses == 5
    assert cfg.frequent_window_days == 90
    assert cfg.volatile_categories == (
        ("copper", 30),
        ("lumber", 30),
        ("sheet_goods", 30),
    )
    assert cfg.high_value_threshold_cents == 10_000
    assert cfg.high_value_interval_days == 60


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"normal_interval_days": 0}, "INTERVAL_INVALID"),
        ({"frequent_interval_days": 0}, "INTERVAL_INVALID"),
        ({"high_value_interval_days": 0}, "INTERVAL_INVALID"),
        ({"volatile_categories": (("copper", 0),)}, "INTERVAL_INVALID"),
        ({"frequent_min_uses": 0}, "FREQUENT_RULE_INVALID"),
        ({"frequent_window_days": 0}, "FREQUENT_RULE_INVALID"),
        ({"high_value_threshold_cents": 0}, "HIGH_VALUE_THRESHOLD_INVALID"),
        ({"volatile_categories": (("Copper", 30),)}, "CATEGORY_KEY_INVALID"),
        ({"volatile_categories": (("", 30),)}, "CATEGORY_KEY_INVALID"),
        (
            {"volatile_categories": (("copper", 30), ("copper", 45))},
            "CATEGORY_KEY_DUPLICATE",
        ),
    ],
)
def test_config_validation(kwargs: dict[str, object], code: str) -> None:
    with pytest.raises(PricingPolicyError) as excinfo:
        RefreshPolicyConfig(**kwargs)  # type: ignore[arg-type]
    assert excinfo.value.code == code


def test_config_validation_bool_type_error() -> None:
    with pytest.raises(TypeError):
        RefreshPolicyConfig(normal_interval_days=True)


def test_classify_normal() -> None:
    policy = RefreshPolicy()
    s = subject(category_key="paint", package_price_cents=4_998, uses_in_window=2)
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.NORMAL
    assert choice.interval_days == 180


def test_classify_frequent_boundary() -> None:
    policy = RefreshPolicy()
    s = subject(category_key="plumbing", package_price_cents=3_497, uses_in_window=5)
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.FREQUENT
    assert choice.interval_days == 90

    s2 = subject(category_key="plumbing", package_price_cents=3_497, uses_in_window=4)
    choice2 = policy.classify(s2)
    assert choice2.refresh_class == RefreshClass.NORMAL
    assert choice2.interval_days == 180


def test_classify_volatile_and_key_normalization() -> None:
    policy = RefreshPolicy()
    s = subject(category_key="copper", package_price_cents=8_950, uses_in_window=0)
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.VOLATILE
    assert choice.interval_days == 30

    s2 = subject(category_key=" Copper ", package_price_cents=8_950, uses_in_window=0)
    choice2 = policy.classify(s2)
    assert choice2.refresh_class == RefreshClass.VOLATILE
    assert choice2.interval_days == 30


def test_classify_high_value_boundary() -> None:
    policy = RefreshPolicy()
    s = subject(category_key="fixtures", package_price_cents=10_000, uses_in_window=0)
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.HIGH_VALUE
    assert choice.interval_days == 60

    s2 = subject(category_key="fixtures", package_price_cents=9_999, uses_in_window=0)
    choice2 = policy.classify(s2)
    assert choice2.refresh_class == RefreshClass.NORMAL
    assert choice2.interval_days == 180

    s3 = subject(category_key="fixtures", package_price_cents=None, uses_in_window=0)
    choice3 = policy.classify(s3)
    assert choice3.refresh_class == RefreshClass.NORMAL
    assert choice3.interval_days == 180


def test_classify_shortest_wins() -> None:
    policy = RefreshPolicy()
    s = subject(category_key="lumber", package_price_cents=12_500, uses_in_window=10)
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.VOLATILE
    assert choice.interval_days == 30


def test_classify_tie_precedence() -> None:
    cfg = RefreshPolicyConfig(volatile_categories=(("copper", 60),))
    policy = RefreshPolicy(cfg)
    s = subject(category_key="copper", package_price_cents=15_000, uses_in_window=0)
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.VOLATILE
    assert choice.interval_days == 60


def test_classify_override() -> None:
    policy = RefreshPolicy()
    s = subject(
        category_key="copper",
        package_price_cents=8_950,
        uses_in_window=0,
        override_interval_days=7,
    )
    choice = policy.classify(s)
    assert choice.refresh_class == RefreshClass.OVERRIDE
    assert choice.interval_days == 7


def test_is_due_boundaries_each_class() -> None:
    policy = RefreshPolicy()

    s1 = subject(category_key="paint", package_price_cents=4_998, uses_in_window=2)
    assert policy.is_due(s1, L + 180 * D - 1) is False
    assert policy.is_due(s1, L + 180 * D) is True

    s2 = subject(category_key="plumbing", package_price_cents=3_497, uses_in_window=5)
    assert policy.is_due(s2, L + 90 * D - 1) is False
    assert policy.is_due(s2, L + 90 * D) is True

    s3 = subject(category_key="copper", package_price_cents=8_950, uses_in_window=0)
    assert policy.is_due(s3, L + 30 * D - 1) is False
    assert policy.is_due(s3, L + 30 * D) is True

    s4 = subject(category_key="fixtures", package_price_cents=10_000, uses_in_window=0)
    assert policy.is_due(s4, L + 60 * D - 1) is False
    assert policy.is_due(s4, L + 60 * D) is True


def test_is_due_stored_next_authoritative() -> None:
    policy = RefreshPolicy()

    s1 = subject(
        category_key="paint",
        package_price_cents=4_998,
        uses_in_window=2,
        next_refresh_at=L + 10 * D,
    )
    assert policy.is_due(s1, L + 10 * D - 1) is False
    assert policy.is_due(s1, L + 10 * D) is True

    s2b = subject(
        category_key="plumbing",
        package_price_cents=3_497,
        uses_in_window=5,
        next_refresh_at=L + 180 * D,
    )
    assert policy.is_due(s2b, L + 90 * D) is False


def test_is_due_status_gates() -> None:
    policy = RefreshPolicy()

    s_ok = subject(last_checked_at=None, refresh_status=RefreshStatus.OK)
    assert policy.is_due(s_ok, L) is True

    s_pending = subject(last_checked_at=None, refresh_status=RefreshStatus.PENDING)
    assert policy.is_due(s_pending, L) is False

    s_failed = subject(last_checked_at=None, refresh_status=RefreshStatus.FAILED)
    assert policy.is_due(s_failed, L) is False

    s_disabled = subject(last_checked_at=None, refresh_status=RefreshStatus.DISABLED)
    assert policy.is_due(s_disabled, L) is False

    s_disabled2 = subject(last_checked_at=L, refresh_status=RefreshStatus.DISABLED)
    assert policy.is_due(s_disabled2, L + 1000 * D) is False


def test_next_refresh_at_each_class() -> None:
    policy = RefreshPolicy()
    C = 1_780_000_000

    s1 = subject(category_key="paint", package_price_cents=4_998, uses_in_window=2)
    assert policy.next_refresh_at(s1, C) == 1_795_552_000

    s2 = subject(category_key="plumbing", package_price_cents=3_497, uses_in_window=5)
    assert policy.next_refresh_at(s2, C) == 1_787_776_000

    s3 = subject(category_key="copper", package_price_cents=8_950, uses_in_window=0)
    assert policy.next_refresh_at(s3, C) == 1_782_592_000

    s4 = subject(category_key="fixtures", package_price_cents=10_000, uses_in_window=0)
    assert policy.next_refresh_at(s4, C) == 1_785_184_000

    s6 = subject(
        category_key="copper",
        package_price_cents=8_950,
        uses_in_window=0,
        override_interval_days=7,
    )
    assert policy.next_refresh_at(s6, C) == 1_780_604_800

    s2b = subject(category_key="plumbing", package_price_cents=3_497, uses_in_window=5)
    assert policy.next_refresh_at(s2b, L) == 1_767_776_000


def test_subject_validation() -> None:
    policy = RefreshPolicy()

    with pytest.raises(PricingPolicyError) as excinfo:
        policy.classify(subject(uses_in_window=-1))
    assert excinfo.value.code == "SUBJECT_INVALID"

    with pytest.raises(PricingPolicyError) as excinfo:
        policy.classify(subject(package_price_cents=-1))
    assert excinfo.value.code == "SUBJECT_INVALID"

    with pytest.raises(PricingPolicyError) as excinfo:
        policy.classify(subject(override_interval_days=0))
    assert excinfo.value.code == "SUBJECT_INVALID"

    with pytest.raises(TypeError):
        policy.is_due(subject(), True)  # type: ignore[arg-type]


def test_search_cache_fresh() -> None:
    assert is_search_cache_fresh(1_000_000, 1_000_000 + 7 * D - 1, 7) is True
    assert is_search_cache_fresh(1_000_000, 1_604_800, 7) is False
    assert is_search_cache_fresh(1_000_000, 999_000, 7) is True
    with pytest.raises(PricingPolicyError) as excinfo:
        is_search_cache_fresh(1_000_000, 1_000_000, 0)
    assert excinfo.value.code == "MAX_AGE_INVALID"
