"""Paired sign-flip permutation test (Phase 12.9)."""

from __future__ import annotations

import random


def paired_sign_flip_p_value(
    paired_differences: tuple[float, ...],
    *,
    n_permutations: int,
    random_seed: int,
) -> float | None:
    """Monte Carlo two-sided p-value for H0: mean paired difference is zero."""
    n = len(paired_differences)
    if n == 0:
        return None
    observed = abs(sum(paired_differences) / n)
    rng = random.Random(random_seed)
    extreme_count = 0
    for _ in range(n_permutations):
        flipped = [diff if rng.random() < 0.5 else -diff for diff in paired_differences]
        perm_mean = abs(sum(flipped) / n)
        if perm_mean >= observed:
            extreme_count += 1
    return (extreme_count + 1) / (n_permutations + 1)


__all__ = ["paired_sign_flip_p_value"]
