"""Rates with Wilson intervals (copied from the pilot's statistics module; now owned here)."""
from __future__ import annotations

import math
from statistics import NormalDist


def _count(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


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
