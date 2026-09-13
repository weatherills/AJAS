# Rollback playbook

1. Redeploy the previous Container Apps / Function App revision.
2. Unset new `FLAG_*` settings. Assign tenants the **Free** plan if billing misfires.
3. Confirm `GET /api/health` `version` matches the last good changelog entry.
4. Watch golden signals (latency, traffic, errors, saturation) for 15 minutes.
5. If share links were minted on a bad build, revoke them from the tenant that created them.

Client-only rollback: clear `ajas.theme` and `ajas.locale` in the browser.
