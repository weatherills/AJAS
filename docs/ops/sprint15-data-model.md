# Sprint 15 data model

```
jobs ||--o{ aliases : parent
jobs ||--o{ matches : job_id
resumes ||--o{ matches : resume_id
users ||--o{ presets : team_id
```

Company aliases merge into a parent node during backfill. Cursor pagination
keys live on matches.
