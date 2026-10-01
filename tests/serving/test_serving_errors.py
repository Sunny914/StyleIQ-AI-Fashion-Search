"""Tests for Phase 13.1 API error mapping."""

from __future__ import annotations

from productiq.exceptions.base import (
    ConfigurationError,
    DatabaseError,
    QueryRepresentationError,
    RecommendationError,
    RetrievalError,
)
from productiq.serving.errors import (
    ApiErrorCode,
    ApiErrorEnvelope,
    map_exception_to_api_error,
    safe_client_message,
)


def test_map_validation_to_invalid_request() -> None:
    body = map_exception_to_api_error(QueryRepresentationError("bad query"), request_id="req-1")
    assert body.code is ApiErrorCode.INVALID_REQUEST
    assert body.request_id == "req-1"
    assert "bad query" in body.message


def test_map_retrieval_error() -> None:
    body = map_exception_to_api_error(RetrievalError("contract violation"))
    assert body.code is ApiErrorCode.INTERNAL_ERROR


def test_map_configuration_error() -> None:
    body = map_exception_to_api_error(ConfigurationError("missing setting"))
    assert body.code is ApiErrorCode.CONFIGURATION_ERROR


def test_map_database_error() -> None:
    body = map_exception_to_api_error(DatabaseError("connection failed"))
    assert body.code is ApiErrorCode.SERVICE_UNAVAILABLE


def test_map_recommendation_error() -> None:
    body = map_exception_to_api_error(RecommendationError("seed invalid"))
    assert body.code is ApiErrorCode.INTERNAL_ERROR


def test_map_unknown_exception_is_internal() -> None:
    body = map_exception_to_api_error(RuntimeError("secret internals"))
    assert body.code is ApiErrorCode.INTERNAL_ERROR
    assert body.message == "An unexpected error occurred"


def test_error_envelope_shape() -> None:
    body = map_exception_to_api_error(ValueError("top_k invalid"), request_id="abc")
    envelope = ApiErrorEnvelope(error=body)
    dumped = envelope.model_dump(mode="json")
    assert dumped["error"]["code"] == "INVALID_REQUEST"
    assert dumped["error"]["request_id"] == "abc"


def test_safe_client_message_strips_empty_productiq_error() -> None:
    assert safe_client_message(RecommendationError("")) == "RecommendationError"
