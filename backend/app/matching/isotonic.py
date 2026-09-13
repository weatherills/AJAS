"""Isotonic regression scaffold with a holdout split (no trained model)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalibrationSplit:
    train: list[tuple[float, float]]
    holdout: list[tuple[float, float]]


def holdout_split(pairs: list[tuple[float, float]], *, holdout_frac: float = 0.2) -> CalibrationSplit:
    if not pairs:
        return CalibrationSplit(train=[], holdout=[])
    cut = max(1, int(len(pairs) * (1.0 - holdout_frac))) if len(pairs) > 1 else 1
    if cut >= len(pairs):
        cut = len(pairs) - 1 if len(pairs) > 1 else 1
    return CalibrationSplit(train=list(pairs[:cut]), holdout=list(pairs[cut:]))


def isotonic_fit(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Pool Adjacent Violators: non-decreasing mapping from score → label."""
    ordered = sorted(((float(x), float(y)) for x, y in pairs), key=lambda item: item[0])
    if not ordered:
        return []
    blocks: list[list[tuple[float, float]]] = [[ordered[0]]]
    for point in ordered[1:]:
        blocks.append([point])
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            left_mean = sum(y for _, y in left) / len(left)
            right_mean = sum(y for _, y in right) / len(right)
            if left_mean <= right_mean:
                break
            blocks[-2] = left + right
            blocks.pop()
    fitted: list[tuple[float, float]] = []
    for block in blocks:
        mean = sum(y for _, y in block) / len(block)
        for x, _ in block:
            fitted.append((x, round(mean, 4)))
    return fitted


def isotonic_predict(fitted: list[tuple[float, float]], score: float) -> float:
    if not fitted:
        return score
    if score <= fitted[0][0]:
        return fitted[0][1]
    for index, (x, y) in enumerate(fitted):
        if score == x:
            return y
        if score < x:
            prev_x, prev_y = fitted[index - 1]
            span = x - prev_x or 1.0
            ratio = (score - prev_x) / span
            return round(prev_y + ratio * (y - prev_y), 4)
    return fitted[-1][1]
