"""Domain unit tests: pure Product behavior, no IO, milliseconds each."""

from __future__ import annotations

import pytest

from atlas_catalog.domain import (
    ConcurrencyError,
    CorrelationId,
    IdempotencyKey,
    InvalidTransition,
    Product,
    ProductId,
    ValidationError,
)


def _create(title: dict[str, str] | None = None) -> Product:
    """Default valid product; pass title to exercise the invalid class."""
    return Product.create(
        product_id=ProductId("product-1"),
        title={"pt-BR": "Café"} if title is None else title,
        category_id=None,
        idempotency_key=IdempotencyKey("idem-1"),
        correlation_id=CorrelationId("corr-1"),
    )


class TestCreate:
    def test_happy_path_starts_as_draft_v1(self) -> None:
        """Given valid pt-BR input / When created / Then DRAFT v1 + event."""
        product = _create()
        assert (product.status, product.version) == ("DRAFT", 1)
        assert [e.event_type for e in product.events] == ["ProductCreated"]

    def test_missing_default_locale_is_rejected(self) -> None:
        """Given title without pt-BR / When created / Then ValidationError."""
        with pytest.raises(ValidationError):
            _create(title={"en-US": "Coffee"})


class TestPublish:
    def test_happy_path_confirms_with_event(self) -> None:
        """Given DRAFT / When published / Then PUBLISHED v2 + event."""
        product = _create()
        event = product.publish(CorrelationId("corr-2"))
        assert (product.status, product.version) == ("PUBLISHED", 2)
        assert event.event_type == "ProductPublished"
        assert event.aggregate_version == 2

    def test_double_publish_is_rejected(self) -> None:
        """Given PUBLISHED / When published again / Then InvalidTransition."""
        product = _create()
        product.publish(CorrelationId("corr-2"))
        with pytest.raises(InvalidTransition):
            product.publish(CorrelationId("corr-3"))

    def test_event_carries_causation_link(self) -> None:
        """Given created+published / When inspected / Then causation chains."""
        product = _create()
        published = product.publish(CorrelationId("corr-2"))
        assert published.causation_id == product.events[0].event_id


class TestConcurrencyErrorShape:
    def test_carries_versions_not_strings(self) -> None:
        """Given conflict data / When raised / Then typed fields preserved."""
        err = ConcurrencyError(expected_version=1, actual_version=2)
        assert (err.expected_version, err.actual_version) == (1, 2)
        assert "expected=1 actual=2" in str(err)
