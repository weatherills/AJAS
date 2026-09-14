# Sprint 17 API cookbook

```bash
curl -s localhost:7071/api/v1/s17/status
curl -s localhost:7071/api/v1/s17/health
curl -s localhost:7071/api/v1/s17/kanban
curl -s 'localhost:7071/api/v1/s17/traces?traceId=s17' -H 'Authorization: Bearer ada'
curl -s localhost:7071/api/v1/sources/status -H 'Authorization: Bearer ada'
curl -s localhost:7071/api/v1/matches -H 'Authorization: Bearer ada'
```

Live fetch: Greenhouse and Lever only. Do not enable extra adapter flags.
