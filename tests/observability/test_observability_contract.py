"""Tests for Phase 13.9.1 observability contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from productiq.api.context import clear_request_id, set_request_id
from productiq.exceptions.base import ValidationError as ProductIQValidationError
from productiq.observability.context import build_observability_context
from productiq.observability.events import (
    ObservabilityEvent,
    ObservabilityEventName,
    ObservabilityOutcome,
    assert_registered_event_name,
    validate_event_metadata,
)
from productiq.observability.metrics import MetricName, MetricObservation, validate_metric_labels
from productiq.observability.tracing import ObservabilitySpan, SpanKind
from productiq.observability.versioning import OBSERVABILITY_CONTRACT_VERSION
from productiq.serving.errors import ApiErrorCode


def test_contract_version_is_semver_like() -> None:
    assert OBSERVABILITY_CONTRACT_VERSION == "1.0.0"


def test_event_names_are_stable_and_registered() -> None:
    assert ObservabilityEventName.API_REQUEST_COMPLETED.value == "api.request.completed"
    with pytest.raises(ProductIQValidationError, match="unregistered"):
        assert_registered_event_name("custom.event")


def test_event_schema_round_trip_json() -> None:
    event = ObservabilityEvent(
        timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
        event_name=ObservabilityEventName.SEARCH_REQUEST_COMPLETED,
        request_id="req-1",
        service_name="productiq",
        operation="search",
        outcome=ObservabilityOutcome.SUCCESS,
        duration_ms=12.5,
        metadata={"result_count": 10, "top_k": 20},
    )
    restored = ObservabilityEvent.model_validate_json(event.model_dump_json())
    assert restored == event


def test_event_rejects_prohibited_metadata_key() -> None:
    with pytest.raises(ProductIQValidationError, match="prohibited"):
        validate_event_metadata({"query": "shoes"})


def test_event_rejects_unknown_metadata_key() -> None:
    with pytest.raises(ProductIQValidationError, match="allowlist"):
        validate_event_metadata({"result_count": 3, "unknown_field": 1})


def test_event_accepts_bounded_metadata() -> None:
    validate_event_metadata({"query_length": 12, "filter_count": 2, "result_count": 5})


def test_event_error_code_uses_api_taxonomy() -> None:
    event = ObservabilityEvent(
        timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
        event_name=ObservabilityEventName.API_REQUEST_FAILED,
        service_name="productiq",
        operation="search",
        outcome=ObservabilityOutcome.FAILURE,
        error_code=ApiErrorCode.NOT_FOUND,
    )
    assert event.error_code is ApiErrorCode.NOT_FOUND


def test_request_context_reads_api_request_id() -> None:
    set_request_id("ctx-req-9")
    try:
        ctx = build_observability_context(operation="product.get")
        assert ctx.request_id == "ctx-req-9"
        assert ctx.service_name == "productiq"
    finally:
        clear_request_id()


def test_request_context_explicit_request_id_override() -> None:
    set_request_id("ignored")
    try:
        ctx = build_observability_context(operation="health", request_id="explicit")
        assert ctx.request_id == "explicit"
    finally:
        clear_request_id()


def test_metric_labels_reject_high_cardinality() -> None:
    with pytest.raises(ProductIQValidationError, match="high-cardinality"):
        validate_metric_labels(
            MetricName.SEARCH_REQUESTS_TOTAL,
            {"operation": "search", "request_id": "abc"},
        )


def test_metric_labels_must_match_allowlist() -> None:
    with pytest.raises(ProductIQValidationError, match="not allowed"):
        validate_metric_labels(MetricName.PRODUCT_REQUESTS_TOTAL, {"endpoint": "product"})


def test_metric_observation_valid_labels() -> None:
    obs = MetricObservation(
        name=MetricName.API_REQUESTS_TOTAL,
        value=1.0,
        labels={"endpoint": "search", "operation": "search", "status_class": "2xx", "outcome": "success"},
    )
    assert obs.name == MetricName.API_REQUESTS_TOTAL


def test_metric_observation_immutable() -> None:
    obs = MetricObservation(
        name=MetricName.PRODUCT_DURATION_MS,
        value=3.0,
        labels={"operation": "get", "outcome": "success"},
    )
    with pytest.raises(PydanticValidationError):
        obs.value = 4.0  # type: ignore[misc]


def test_span_contract_serialization() -> None:
    span = ObservabilitySpan(
        span_name="search.serving",
        kind=SpanKind.SERVING,
        started_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        duration_ms=1.0,
        request_id="r1",
        operation="search",
    )
    payload = json.loads(span.model_dump_json())
    assert payload["kind"] == "serving"


def test_create_app_still_imports_without_observability_backend() -> None:
    from productiq.api.app import create_app
    from tests.api.fakes import RecordingSearchService

    app = create_app(search_service=RecordingSearchService())
    assert app.title == "ProductIQ API"
