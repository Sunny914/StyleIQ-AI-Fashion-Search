"""Document and guard opt-in integration/smoke environment flags (Phase 13.7)."""

from __future__ import annotations

from tests.api.test_application_production_smoke import APPLICATION_COMPOSITION_SMOKE_ENV
from tests.api.test_recommendation_integration import RECOMMENDATION_API_SMOKE_ENV_VAR
from tests.api.test_search_integration import SEARCH_API_SMOKE_ENV_VAR
from tests.database.test_integration import INTEGRATION_ENV_VAR
from tests.retrieval.integration.conftest import PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR


def test_documented_opt_in_flags_are_stable_strings() -> None:
    """Regression guard: renames break CI/docs; keep names stable or update architecture docs."""
    assert INTEGRATION_ENV_VAR == "PRODUCTIQ_RUN_INTEGRATION_TESTS"
    assert SEARCH_API_SMOKE_ENV_VAR == "PRODUCTIQ_SEARCH_API_SMOKE"
    assert PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR == "PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE"
    assert APPLICATION_COMPOSITION_SMOKE_ENV == "PRODUCTIQ_APPLICATION_COMPOSITION_SMOKE"
    assert RECOMMENDATION_API_SMOKE_ENV_VAR == "PRODUCTIQ_RECOMMENDATION_API_SMOKE"
    from productiq.serving.performance.search_benchmark import SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV

    assert SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV == "PRODUCTIQ_SEARCH_SERVING_PERFORMANCE_BENCHMARK"
