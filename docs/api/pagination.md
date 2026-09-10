# Pagination and filtering

All list endpoints accept:

| Param | Alias | Notes |
| --- | --- | --- |
| `limit` | `pageSize` | 1–100, default 25 |
| `cursor` | `continuation` | Opaque; omit on the first page |

Responses include `items` and `nextCursor` (null/omitted when done). Review also
returns `continuationToken` as an alias of `nextCursor`.

Discover the contract at runtime: `GET /api/v1/meta/pagination`.
