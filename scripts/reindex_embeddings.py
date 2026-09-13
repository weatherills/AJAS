"""CLI: reindex embeddings for persisted match runs (no-op without OpenAI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.matching.embedder import default_embedder  # noqa: E402
from app.matching.runtime import try_get_service  # noqa: E402


def main() -> None:
    embedder = default_embedder()
    service = try_get_service()
    count = 0
    if service is not None:
        for run in service.store.list_runs("local-user", include_expired=True):
            text = f"{run.resume_hash or ''} {run.job_hash or ''}"
            embedder.embed([text])
            count += 1
    print(json.dumps({"reindexed": count, "embedder": type(embedder).__name__}))


if __name__ == "__main__":
    main()
