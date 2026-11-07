"""Rates and calibration thresholds (copied from the pilot's statistics module; now owned here).

Alarm semantics are always ``score >= threshold``. Missing measurements are
never zeros.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Iterable


def _count(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _finite(values: Iterable[float]) -> list[float]:
    result = [float(x) for x in values]
    if not all(math.isfinite(x) for x in result):
        raise ValueError("measurements must be finite; filter missing results explicitly")
    return result


def binomial_rate(count: int, n: int, confidence: float = .95) -> dict:
    """Count/rate and a two-sided Wilson score interval (no continuity correction)."""
    _count(count, "count")
    _count(n, "n")
    if count > n or not 0 < confidence < 1:
        raise ValueError("require 0 <= count <= n and 0 < confidence < 1")
    if not n:
        return {"count": count, "n": n, "rate": None, "ci95": None, "confidence": confidence}
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    rate = count / n
    denominator = 1 + z * z / n
    center = (rate + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
    return {"count": count, "n": n, "rate": rate,
            "ci95": [0. if count == 0 else max(0., center - radius),
                     1. if count == n else min(1., center + radius)], "confidence": confidence}


def calibration_threshold(scores: Iterable[float], target_fpr: float = .05) -> float | None:
    """Choose the lowest representable conservative empirical alarm threshold.

    At most floor(n*target_fpr) calibration scores may meet/exceed it. Ties at
    the selected order statistic are excluded together using nextafter, rather
    than accidentally exceeding the target. Empty input returns None: there is
    no calibrated threshold. This is an empirical constraint, not a population
    FPR guarantee.
    """
    values = sorted(_finite(scores))
    if not math.isfinite(target_fpr) or not 0 <= target_fpr <= 1:
        raise ValueError("target_fpr must be in [0, 1]")
    if not values:
        return None
    permitted = math.floor(len(values) * target_fpr)
    if permitted == len(values):
        return values[0]
    return math.nextafter(values[len(values) - permitted - 1], math.inf)
