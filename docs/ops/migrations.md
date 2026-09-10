# Online migrations (zero downtime)

AJAS containers are created with `create_container_if_not_exists` in each
feature's `containers.py`. Treat schema changes as **expand / contract**:

1. **Expand** — add optional fields or new containers. Never rename or drop a
   partition key. Run `python scripts/migration_check.py` in CI.
2. **Dual-write** — application code reads old and new fields.
3. **Backfill** — `POST /api/v1/learning/pipeline/backfill` for learning events;
   other entities use in-process seed (`POST /api/v1/ops/seed`) locally.
4. **Contract** — only after a full release cycle, stop reading the old field.

Forbidden in this repo: `delete_container` / `delete_database` from app code.

Cosmos production: enable periodic or continuous backup before a dual-write
release. See [backups.md](backups.md).
