# Disaster recovery

Extends [backups.md](./backups.md).

| Store | RPO | RTO |
| --- | --- | --- |
| Cosmos | 1 hour | 30 minutes |
| Blob | 1 hour | 30 minutes |
| In-process demo | none (restart wipes) | re-run `python scripts/seed_demo.py` |

Drill:

1. Snapshot Cosmos to `ajas-restore-drill`.
2. Copy blob containers to `*-restore`.
3. Point staging Functions at the restored account.
4. `GET /api/health` then `GET /api/v1/settings`.
5. Tear down the drill account. Log date, operator, and duration.

`python scripts/backup_drill.py` appends `docs/ops/restore-drills.log`.
