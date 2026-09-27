import dataclasses

import pytest

from codey_estimator.errors import RetailerAdapterError
from codey_estimator.ports import ObservationSource, PriceObservationData, RetailerProductData
from codey_estimator.retailers.base import (
    AdapterCapability,
    ObservedPrice,
    RetailerAdapter,
    RetailerOffer,
)
from codey_estimator.retailers.csv_import import CsvColumnMapping, CsvImportAdapter
from codey_estimator.retailers.manual import ManualAdapter


def test_observed_price_fields_mirror_price_observation_data():
    price_obs_fields = [f.name for f in dataclasses.fields(PriceObservationData)]
    observed_price_fields = [f.name for f in dataclasses.fields(ObservedPrice)]
    assert price_obs_fields[0] == "retailer_product_id"
    assert price_obs_fields[1:] == observed_price_fields


def test_bind_builds_price_observation_data():
    price = ObservedPrice(
        price_cents=4297,
        observed_at=1789918200,
        source=ObservationSource.MANUAL,
        observed_by_user_id=3,
    )
    assert price.bind(41) == PriceObservationData(
        retailer_product_id=41,
        price_cents=4297,
        observed_at=1789918200,
        source=ObservationSource.MANUAL,
        observed_by_user_id=3,
    )


def test_bind_rejects_bad_ids():
    price = ObservedPrice(price_cents=100, observed_at=0, source=ObservationSource.MANUAL)
    with pytest.raises(TypeError):
        price.bind(True)
    with pytest.raises(TypeError):
        price.bind("1")
    with pytest.raises(ValueError):
        price.bind(0)
    with pytest.raises(ValueError):
        price.bind(-5)


def test_dataclasses_frozen():
    price = ObservedPrice(price_cents=100, observed_at=0, source=ObservationSource.MANUAL)
    with pytest.raises(dataclasses.FrozenInstanceError):
        price.price_cents = 200  # type: ignore[misc]

    offer = RetailerOffer(
        product=RetailerProductData(retailer_code="manual", retailer_sku="s", title="t"),
        price=price,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        offer.price = price  # type: ignore[misc]


class FakeRemoteAdapter:
    @property
    def retailer_code(self) -> str:
        return "fake"

    @property
    def source(self) -> ObservationSource:
        return ObservationSource.ADAPTER

    @property
    def capabilities(self):
        return frozenset({AdapterCapability.SEARCH, AdapterCapability.FETCH_PRICE})

    def search(self, query: str):
        return ()

    def fetch_current_price(self, retailer_sku: str, *, store_code: str | None = None):
        return None


class MissingFetch:
    @property
    def retailer_code(self) -> str:
        return "missing"

    @property
    def source(self) -> ObservationSource:
        return ObservationSource.ADAPTER

    @property
    def capabilities(self):
        return frozenset()

    def search(self, query: str):
        return ()


def test_protocol_isinstance():
    assert isinstance(ManualAdapter(), RetailerAdapter)
    assert isinstance(
        CsvImportAdapter(
            "csv:x",
            CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price"),
        ),
        RetailerAdapter,
    )
    assert isinstance(FakeRemoteAdapter(), RetailerAdapter)
    assert not isinstance(MissingFetch(), RetailerAdapter)


@pytest.mark.parametrize(
    "adapter",
    [
        ManualAdapter(),
        CsvImportAdapter(
            "csv:x",
            CsvColumnMapping(sku_column="SKU", title_column="Title", price_column="Price"),
        ),
    ],
)
def test_unsupported_operations_raise(adapter):
    with pytest.raises(RetailerAdapterError) as exc_info:
        adapter.search("x")
    assert exc_info.value.code == "UNSUPPORTED_OPERATION"

    with pytest.raises(RetailerAdapterError) as exc_info:
        adapter.fetch_current_price("x")
    assert exc_info.value.code == "UNSUPPORTED_OPERATION"

    assert adapter.capabilities == frozenset()


def test_error_hierarchy():
    from codey_estimator.errors import CsvImportError, EstimatorError, RetailerDataError

    data_err = RetailerDataError("INVALID_PRICE", "bad", field="price_cents")
    assert isinstance(data_err, EstimatorError)
    assert isinstance(data_err, ValueError)
    assert data_err.code == "INVALID_PRICE"
    assert data_err.field == "price_cents"

    csv_err = CsvImportError("MISSING_COLUMN", "bad", columns=("A",), row_number=3)
    assert isinstance(csv_err, EstimatorError)
    assert isinstance(csv_err, ValueError)
    assert csv_err.code == "MISSING_COLUMN"
    assert csv_err.columns == ("A",)
    assert csv_err.row_number == 3

    adapter_err = RetailerAdapterError("UNSUPPORTED_OPERATION", "no")
    assert isinstance(adapter_err, EstimatorError)
    assert adapter_err.code == "UNSUPPORTED_OPERATION"
