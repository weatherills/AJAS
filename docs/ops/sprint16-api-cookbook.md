# Sprint 16 API cookbook

```bash
curl -s localhost:7071/api/v1/s16/status
curl -s localhost:7071/api/v1/s16/health
curl -s 'localhost:7071/api/v1/s16/search?q=%22python%22+NOT+java' -H 'Authorization: Bearer ada'
curl -s 'localhost:7071/api/v1/s16/traces?traceId=s16' -H 'Authorization: Bearer ada'
```

Optional adapters stay off. Do not send live HTML fetches from these helpers.
