"""Small, dependency-free statistics: rates with uncertainty and a paired comparison."""

from __future__ import annotations

import math
from statistics import median

Z95 = 1.959963984540054


def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion (well behaved for small n and rates near 0 or 1)."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for discordant pair counts b and c (binomial, p = 0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def med(values: list[float]) -> float | None:
    return round(median(values), 2) if values else None


def summarize_condition(attempts: list[dict]) -> dict:
    n = len(attempts)
    resolved = sum(a["resolved"] for a in attempts)
    regressions = sum(a["regression"] for a in attempts)
    lo, hi = wilson(resolved, n)
    return {
        "attempts": n,
        "resolved": resolved,
        "resolution_rate": round(resolved / n, 4) if n else None,
        "resolution_ci95": [round(lo, 4), round(hi, 4)],
        "regressions": regressions,
        "regression_rate": round(regressions / n, 4) if n else None,
        "timeouts": sum(a["status"] == "timeout" for a in attempts),
        "errors": sum(a["status"] == "error" for a in attempts),
        "no_change": sum(a["status"] in ("no_change", "unparsable") for a in attempts),
        "median_seconds": med([a["seconds"] for a in attempts]),
        "median_seconds_resolved": med([a["seconds"] for a in attempts if a["resolved"]]),
        "model_calls": sum(a["model_calls"] for a in attempts),
        "tokens_est_total": sum(a["tokens_est"] for a in attempts),
        "tokens_est_median": med([a["tokens_est"] for a in attempts]),
        "cost_usd_est": _sum_or_none([a.get("cost_usd_est") for a in attempts]),
    }


def _sum_or_none(values: list[float | None]) -> float | None:
    if not values or any(v is None for v in values):
        return None
    return round(sum(v for v in values if v is not None), 6)


def paired(attempts: list[dict], a: str = "baseline", b: str = "qedcode") -> dict | None:
    """Compare conditions on the same (task, repetition) pairs; only complete pairs count."""
    by_key: dict[tuple, dict[str, bool]] = {}
    for att in attempts:
        by_key.setdefault((att["task_id"], att["rep"]), {})[att["condition"]] = att["resolved"]
    pairs = [v for v in by_key.values() if a in v and b in v]
    if not pairs:
        return None
    both = sum(v[a] and v[b] for v in pairs)
    only_a = sum(v[a] and not v[b] for v in pairs)
    only_b = sum(v[b] and not v[a] for v in pairs)
    neither = len(pairs) - both - only_a - only_b
    n = len(pairs)
    return {
        "pairs": n,
        "both_resolved": both,
        f"only_{a}": only_a,
        f"only_{b}": only_b,
        "neither": neither,
        "difference": round((only_b - only_a) / n, 4),  # paired rate of b minus rate of a
        "mcnemar_p": round(mcnemar_exact(only_a, only_b), 4),
    }
