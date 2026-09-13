"""Min-max normalize ranking features so mixed sources share a scale."""

from __future__ import annotations

from typing import Any


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    return [(value - lo) / (hi - lo) for value in values]


def normalize_features(rows: list[dict[str, Any]], *, fields: tuple[str, ...] = ("score", "keyword", "semantic")) -> list[dict[str, Any]]:
    columns = {field: _minmax([float(row.get(field) or 0.0) for row in rows]) for field in fields}
    out = []
    for index, row in enumerate(rows):
        fair = dict(row)
        for field in fields:
            fair[f"{field}_norm"] = round(columns[field][index], 4)
        fair["fair_score"] = round(sum(fair[f"{field}_norm"] for field in fields) / len(fields), 4)
        out.append(fair)
    return out
