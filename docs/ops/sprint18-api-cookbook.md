# Sprint 18 API cookbook

```bash
curl -s localhost:7071/api/v1/s18/status
curl -s localhost:7071/api/v1/s18/health
curl -s localhost:7071/api/v1/s18/kanban
curl -s 'localhost:7071/api/v1/s18/traces?traceId=s18' -H 'Authorization: Bearer ada'
curl -s localhost:7071/api/health
```

Live fetch: Greenhouse and Lever only. Do not enable extra adapter flags.
Match persistence threshold default is 70 on a 0–100 scale.
