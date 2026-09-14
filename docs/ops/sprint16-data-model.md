# Sprint 16 data model

```
jobs ||--o{ brands : dba
jobs ||--o{ matches : job_id
resumes ||--o{ matches : resume_id
users ||--o{ presets : org_id
```

Brand/DBA aliases merge into a parent node during backfill. Cursor pagination
v3 keys live on matches.
