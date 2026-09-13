# Release checklist

- [ ] `pytest -n auto` and frontend `npm test` / `tsc --noEmit` / `oxlint` green
- [ ] Optional adapters still default **off**
- [ ] Health `version` matches `CHANGELOG.md`
- [ ] Backup drill logged this month (`python scripts/backup_drill.py`)
- [ ] Rollback owner named
- [ ] Cookie banner and Legal links load
- [ ] Stripe webhook and Google SSO remain stubbed in production unless explicitly contracted
