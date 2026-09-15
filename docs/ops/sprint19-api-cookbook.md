# Sprint 19 API cookbook

```bash
curl -s localhost:7071/api/v1/s19/status
curl -s localhost:7071/api/v1/s19/health
curl -s localhost:7071/api/v1/s19/kanban
curl -s 'localhost:7071/api/v1/s19/traces?traceId=s19' -H 'Authorization: Bearer ada'
curl -s localhost:7071/api/health
```

Live fetch: Greenhouse and Lever only. Do not enable extra adapter flags.
Match persistence threshold default is 70 on a 0–100 scale.
