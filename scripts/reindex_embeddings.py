"""CLI: reindex embeddings for persisted match runs (no-op without OpenAI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.matching.embedder import default_embedder  # noqa: E402
from app.matching.runtime import try_get_service  # noqa: E402


def orchestrate(*, batch_size: int = 25) -> dict:
    embedder = default_embedder()
    service = try_get_service()
    count = 0
    batches = 0
    if service is not None:
        runs = list(service.store.list_runs("local-user", include_expired=True))
        for i in range(0, len(runs), batch_size):
            chunk = runs[i : i + batch_size]
            texts = [f"{run.resume_hash or ''} {run.job_hash or ''}" for run in chunk]
            embedder.embed(texts)
            count += len(chunk)
            batches += 1
    return {"reindexed": count, "batches": batches, "embedder": type(embedder).__name__, "orchestrated": True}


def main() -> None:
    print(json.dumps(orchestrate()))


if __name__ == "__main__":
    main()
