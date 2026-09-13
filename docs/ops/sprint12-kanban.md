# Sprint 12 Kanban log

Landed on `main` as `[S12]` commits.

- [x] 001 Multi-tenant architecture: org/workspace model and data scoping
- [x] 002 Tenant onboarding flow and admin invite emails
- [x] 003 Roles & permissions: RBAC (Owner, Admin, Member, Read-only)
- [x] 004 Access control middleware and permission checks across APIs
- [x] 005 Billing: metered usage counters (ingest/match/apply/email)
- [x] 006 Billing: plan tiers (Free, Pro, Team) with feature gates
- [x] 007 Billing: Stripe subscription + metered billing integration
- [x] 008 Billing: webhook handling and invoice status sync
- [x] 009 Account limits: enforce soft/hard caps with UX messages
- [x] 010 Admin console: tenant usage dashboard and actions

## Batch 1 gate
- tests/lint/typecheck green after task 10
- [x] 011 Data export: user/tenant GDPR bundle (JSON + CSV)
- [x] 012 Data import: upload resume library (PDF, DOCX) with parsing queue
