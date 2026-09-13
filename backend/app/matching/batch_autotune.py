"""Autotune embedding batch size from recent latency samples."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BatchAutotune:
    min_size: int = 4
    max_size: int = 64
    target_ms: float = 250.0
    size: int = 16
    samples: list[float] = field(default_factory=list)

    def record(self, latency_ms: float, *, batch_size: int | None = None) -> int:
        used = batch_size or self.size
        self.samples.append(float(latency_ms))
        if latency_ms > self.target_ms * 1.25 and used > self.min_size:
            self.size = max(self.min_size, used // 2)
        elif latency_ms < self.target_ms * 0.6 and used < self.max_size:
            self.size = min(self.max_size, used * 2)
        return self.size
