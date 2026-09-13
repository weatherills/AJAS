# API cookbook (Sprint 13)

Examples for the search/sort/filter contract and Sprint 13 ops routes.

## List jobs (existing)

```
GET /api/v1/jobs?cursor=0&limit=50&q=python
```

## Sprint 13 search helper

```
GET /api/v1/s13/search?q=staff&sort=title&order=asc
Authorization: Bearer ada
```

Pass `items` as a JSON array when exercising the helper in isolation.

## Chaos and canary

```
POST /api/v1/s13/kill {"name":"ingest","enabled":true}
POST /api/v1/s13/canary {"flag":"fit-v2","percent":10}
GET /api/v1/s13/e2e
GET /api/v1/s13/e2e?mode=retry&failAt=apply
```

## Traces and audit

```
GET /api/v1/s13/traces?traceId=<id>
GET /api/v1/s13/audit?format=json
GET /api/v1/s13/audit?format=csv
```

## Redaction

```
POST /api/v1/s13/redact
{"tenantId":"t1","fields":["email","phone"],"payload":{"email":"a@b.c","title":"Staff"}}
```

## Tenancy (Sprint 12)

```
POST /api/v1/tenants {"name":"Acme"}
POST /api/v1/share/links {"targetType":"match","targetId":"m1"}
```
