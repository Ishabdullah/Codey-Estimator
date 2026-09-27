import dataclasses
from decimal import Decimal

import pytest

from codey_estimator.ports import (
    ObservationSource,
    PriceObservationData,
    PriceObservationRecord,
    PriceObservationRepo,
    RefreshState,
    RetailerProductData,
    RetailerProductRecord,
    RetailerProductRepo,
    SearchCacheEntry,
    SearchCacheRepo,
)
from codey_estimator.refresh import RefreshStatus


class FakeRetailerProductRepo:
    def get_by_sku(self, retailer_code, retailer_sku):
        return None

    def get_by_upc(self, upc, retailer_code=None):
        return ()

    def upsert(self, data, seen_at):
        raise NotImplementedError

    def list_needing_refresh(self, now, limit):
        return ()

    def update_refresh_state(self, product_id, state):
        return None


class FakePriceObservationRepo:
    def append(self, observation):
        raise NotImplementedError

    def get_latest(self, retailer_product_id, store_code=None):
        return None

    def get_history(self, retailer_product_id, *, since=None, limit=None):
        return ()


class FakeSearchCacheRepo:
    def get(self, retailer_code, normalized_query):
        return None

    def put(self, entry):
        return None


def test_retailer_product_repo_protocol():
    assert isinstance(FakeRetailerProductRepo(), RetailerProductRepo)


def test_price_observation_repo_protocol():
    assert isinstance(FakePriceObservationRepo(), PriceObservationRepo)


def test_search_cache_repo_protocol():
    assert isinstance(FakeSearchCacheRepo(), SearchCacheRepo)


def test_missing_method_fails_isinstance():
    class IncompleteRetailerProductRepo:
        def get_by_sku(self, retailer_code, retailer_sku):
            return None

        def get_by_upc(self, upc, retailer_code=None):
            return ()

        def upsert(self, data, seen_at):
            raise NotImplementedError

        def list_needing_refresh(self, now, limit):
            return ()

    assert not isinstance(IncompleteRetailerProductRepo(), RetailerProductRepo)


def test_records_frozen():
    refresh_state = RefreshState()
    with pytest.raises(dataclasses.FrozenInstanceError):
        refresh_state.refresh_priority = 5  # type: ignore[misc]

    data = RetailerProductData(retailer_code="homedepot", retailer_sku="123", title="Widget")
    with pytest.raises(dataclasses.FrozenInstanceError):
        data.title = "Other"  # type: ignore[misc]

    record = RetailerProductRecord(
        id=1,
        data=data,
        current_price_cents=None,
        current_observation_id=None,
        refresh=refresh_state,
        first_seen_at=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.active = False  # type: ignore[misc]

    obs_data = PriceObservationData(
        retailer_product_id=1,
        price_cents=100,
        observed_at=0,
        source=ObservationSource.ADAPTER,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs_data.price_cents = 200  # type: ignore[misc]

    obs_record = PriceObservationRecord(id=1, data=obs_data)
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs_record.id = 2  # type: ignore[misc]

    entry = SearchCacheEntry(
        retailer_code="homedepot",
        normalized_query="paint",
        result_skus=("sku1",),
        fetched_at=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.fetched_at = 1  # type: ignore[misc]


def test_retailer_product_data_has_no_price_or_refresh_fields():
    forbidden = {
        "current_price_cents",
        "current_observation_id",
        "refresh",
        "last_checked_at",
        "next_refresh_at",
    }
    field_names = {f.name for f in dataclasses.fields(RetailerProductData)}
    assert field_names.isdisjoint(forbidden)


def test_enum_values():
    assert ObservationSource.ADAPTER.value == "adapter"
    assert ObservationSource.MANUAL.value == "manual"
    assert ObservationSource.CSV.value == "csv"

    assert RefreshStatus.OK.value == "ok"
    assert RefreshStatus.PENDING.value == "pending"
    assert RefreshStatus.FAILED.value == "failed"
    assert RefreshStatus.DISABLED.value == "disabled"


def test_package_qty_is_decimal():
    data = RetailerProductData(retailer_code="homedepot", retailer_sku="123", title="Widget")
    assert data.package_qty == Decimal(1)
