# Release and rollback v2

1. Keep optional adapter flags off.
2. Deploy Azure Functions + frontend together.
3. If health.version is wrong, `git revert` the release commit and redeploy.
4. Fixture-only adapters do not need outbound allowlist changes.
