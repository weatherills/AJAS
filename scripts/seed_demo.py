#!/usr/bin/env python3
"""Print how to seed the local AJAS demo (no Cosmos)."""

from __future__ import annotations

HELP = """
AJAS local demo

1. Backend (from repo root):
     source /workspace/.venv/bin/activate
     cd backend && func start
   AUTH_MODE=dev accepts Authorization: Bearer local-user

2. Frontend:
     cd frontend && npm run dev
   Open http://localhost:3000  (Vite proxies /api → 127.0.0.1:7071)

3. Demo data is created in-process:
   - Resume library seeds an active resume
   - Job sources with demo_seed skip live HTTP and keep sample boards
   - Email uses the local demo mailbox until Graph is connected
   - Review / Learning seed rows for local-user

4. First-run checklist is on the home page. Walk:
   Settings (threshold + a board) → Jobs → Review → Apply/Email.

There is no Cosmos dump to import. Restarting Azure Functions clears memory stores.
"""


def main() -> None:
    print(HELP.strip())


if __name__ == "__main__":
    main()
