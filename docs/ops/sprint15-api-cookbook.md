# Sprint 15 API cookbook

```bash
curl -s localhost:7071/api/v1/s15/kanban
curl -s localhost:7071/api/v1/s15/status
curl -s localhost:7071/api/v1/s15/health
curl -s 'localhost:7071/api/v1/s15/search?q=python+AND+azure' -H 'Authorization: Bearer ada'
curl -s 'localhost:7071/api/v1/s15/traces?traceId=s15' -H 'Authorization: Bearer ada'
```

Optional adapters stay off. Do not send live HTML fetches from these helpers.
