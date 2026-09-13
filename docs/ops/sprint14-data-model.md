# Data model (Sprint 14)

```
jobs ||--o{ matches : job_id
resumes ||--o{ matches : resume_id
users ||--o{ matches : user_id
jobs ||--o{ emails : thread
```

Jobs keep salary/geo/skills on the posting document. Matches store keyword/semantic/recency sub-scores.
