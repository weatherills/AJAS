"""Brute-force ANN stand-in with recall@k evaluation harness."""

from __future__ import annotations

import math
from typing import Sequence

from app.matching.vectors import VectorStore


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _norm(vec: Sequence[float]) -> float:
    return math.sqrt(sum(v * v for v in vec)) or 1.0


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return _dot(left, right) / (_norm(left) * _norm(right))


def search(store: VectorStore, query: Sequence[float], *, k: int = 5) -> list[tuple[str, float]]:
    scored = []
    for doc_id, vector in store.live.items():
        if doc_id in store.tombstones:
            continue
        scored.append((doc_id, cosine(query, vector)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


def recall_at_k(predicted: list[str], relevant: list[str], *, k: int) -> float:
    if not relevant:
        return 0.0
    hit = len(set(predicted[:k]) & set(relevant))
    return hit / len(relevant)


def evaluate_recall(store: VectorStore, queries: list[dict], *, k: int = 3) -> dict[str, float]:
    scores = []
    for row in queries:
        ranked = [doc_id for doc_id, _ in search(store, row["vector"], k=k)]
        scores.append(recall_at_k(ranked, list(row["relevant"]), k=k))
    return {"k": float(k), "recall": sum(scores) / len(scores) if scores else 0.0, "n": float(len(scores))}
