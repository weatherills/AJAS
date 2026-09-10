# Backups and restore drill

## Targets

- **Cosmos DB** (`ajas` database): user settings, matches, applications, mail metadata.
- **Blob Storage**: resume PDFs, cover letters, raw job payloads, mail attachments.
- **Queues**: ephemeral; do not restore poison messages.

## RPO / RTO

| Store | RPO (max data loss) | RTO (restore time) |
| --- | --- | --- |
| Cosmos | 1 hour (periodic backup / continuous if enabled) | 30 minutes to a new account + connection-string swap |
| Blob | 1 hour | 30 minutes via container copy |

## Scheduled backups

Enable Cosmos periodic backup (or continuous mode) on the `ajas` account. Enable blob
soft-delete (7+ days) and versioning on `resumes`, `mail-attachments`, and `job-raw`.

## Restore drill (staging)

1. Snapshot Cosmos to a new database `ajas-restore-drill`.
2. Copy blob containers to `*-restore`.
3. Point a staging Function App at the restored account.
4. `GET /api/health` then `GET /api/v1/settings` as `local-user`.
5. Confirm Review queue loads and a resume preview URL still opens.
6. Tear down the drill account. Log date, operator, and duration in the runbook notes.

Local (no Cosmos): data lives in-process. Restarting Functions is a full wipe — use
`scripts/seed_demo.py` after restart.
