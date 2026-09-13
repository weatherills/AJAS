# Adapter authoring v2

Fixture-only HTML/JSON parsers. Respect robots.txt. Feature flags default **off**.

## Rules

1. Parse `backend/tests/fixtures/job_boards/` snapshots. Do not fetch live HTML.
2. Record success/error rates via `app.sprint13.ingest.frontier_score`.
3. On 403/block pages, cool down. Open the circuit only on **5xx**.
4. Captcha or session expiry → fixture fallback. Never set `bypass: true`.
5. Dual-path parsers (Indeed JSON + HTML) must tag `via` on each row.
6. Keep secrets out of logs; run `python scripts/s13_pii_scan.py` in CI.

## Checklist

- Fixture `.html` plus `.sha256` (or `.json` for API-shaped boards).
- Source flag in `app.flags.FLAG_DEFAULTS` stays false until reviewed.
- Unit test with the snapshot, no network.
- Document robots/consent for the host.
