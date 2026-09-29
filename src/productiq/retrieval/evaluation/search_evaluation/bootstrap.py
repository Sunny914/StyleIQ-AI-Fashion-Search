"""Paired query-level bootstrap confidence intervals (Phase 12.9)."""

from __future__ import annotations

import random

from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    BootstrapConfiguration,
    ConfidenceInterval,
)


def bootstrap_mean_ci(
    paired_differences: tuple[float, ...],
    configuration: BootstrapConfiguration,
) -> ConfidenceInterval | None:
    """Percentile bootstrap CI for the mean paired difference."""
    n = len(paired_differences)
    if n == 0:
        return None
    rng = random.Random(configuration.random_seed)
    bootstrap_means: list[float] = []
    for _ in range(configuration.n_bootstrap_samples):
        sample = [paired_differences[rng.randrange(n)] for _ in range(n)]
        bootstrap_means.append(sum(sample) / n)
    bootstrap_means.sort()
    alpha = 1.0 - configuration.confidence_level
    lower_index = int((alpha / 2) * configuration.n_bootstrap_samples)
    upper_index = int((1.0 - alpha / 2) * configuration.n_bootstrap_samples) - 1
    lower_index = max(0, min(lower_index, len(bootstrap_means) - 1))
    upper_index = max(0, min(upper_index, len(bootstrap_means) - 1))
    return ConfidenceInterval(
        confidence_level=configuration.confidence_level,
        lower=bootstrap_means[lower_index],
        upper=bootstrap_means[upper_index],
        method=configuration.ci_method,
    )


__all__ = ["bootstrap_mean_ci"]
