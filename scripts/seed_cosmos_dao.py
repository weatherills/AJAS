#!/usr/bin/env python3
"""Minimal Cosmos DAO seeds: user settings, a resume, a job, a match sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.storage.dao import domain_daos, ensure_mvp_containers, seed_dao_defaults
from app.storage.dal import CosmosDAL
from app.storage.seeds import SEED_JOB_ID, SEED_RESUME_ID, SEED_USER_ID, apply_seed
from app.storage.testing import FakeDatabase


def seed(database=None) -> dict:
    db = database or FakeDatabase()
    ensure_mvp_containers(db)
    dal = CosmosDAL(db)
    counts = apply_seed(dal)
    defaults = seed_dao_defaults(dal, SEED_USER_ID)
    daos = domain_daos(dal)
    resume = daos["resumes"].create_resume(
        SEED_USER_ID,
        id=f"{SEED_RESUME_ID}-dao",
        original_filename="dao-seed.pdf",
        blob_uri=f"{SEED_USER_ID}/{SEED_RESUME_ID}-dao/dao-seed.pdf",
    )
    posting = daos["job_ingest"].upsert_posting(
        canonical_key="staff-platform-engineer|seattle-wa|acme",
        title="Staff Platform Engineer",
        company="Acme",
        source="greenhouse",
        id=SEED_JOB_ID,
    )
    match = daos["matching"].create_match_record(
        SEED_USER_ID,
        job_id=SEED_JOB_ID,
        resume_id=SEED_RESUME_ID,
        score=91.0,
        evidence=["Kubernetes production ownership"],
    )
    return {
        "schema": "ajas.dao.seed.v1",
        "catalog": counts,
        "defaults": {key: defaults[key].get("id") for key in defaults if isinstance(defaults[key], dict)},
        "resumeId": resume["id"],
        "jobId": posting["item"]["id"],
        "matchId": match["record"]["id"],
    }


def main() -> int:
    print(json.dumps(seed(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
