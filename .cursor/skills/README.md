# CodeSpring skills (vendored)

These agent skills are vendored from
[`CodeSpringApp/codespring-skills`](https://github.com/codespringapp/codespring-skills)
(Apache-2.0). They let a coding agent do CodeSpring project planning and
management — importing a codebase, generating PRDs, creating tasks, building
features, resyncing the CodeSpring map, and related marketing/SEO helpers.

- **Source:** https://github.com/codespringapp/codespring-skills
- **Pinned commit:** `cd09e131d480f746e6ad4e1bb298f8f8fcb35b95`
- **Installed via the upstream layout:** each `skills/<name>/` was copied to
  `.cursor/skills/<name>/` (equivalent to `npx skills add CodeSpringApp/codespring-skills`
  choosing the Cursor target). This directory is not a skill itself.

## Usage

Cursor auto-loads every `.cursor/skills/<name>/SKILL.md`. The agent invokes a
skill when relevant, or you can run one manually in Agent chat with `/<name>`,
e.g. `/codespring`, `/cs-build-getting-started`, `/cs-build-resync-codebase`.

Most skills require the CodeSpring CLI to be installed and authenticated on the
machine running the agent:

```bash
npm i -g @codespring-app/cli
codespring auth login
```

## Updating

Re-run the upstream installer (`npx skills add CodeSpringApp/codespring-skills`)
or re-copy `skills/*` from the source repo, and bump the pinned commit above.
