"""Resume Management database constants (Database PRD)."""

from typing import Final, Literal

ProcessingStatus = Literal["uploaded", "queued", "parsing", "parsed", "failed"]
ChildSource = Literal["parsed", "manual"]
ParseEventType = Literal[
    "uploaded",
    "queued",
    "started",
    "succeeded",
    "failed",
    "duplicate_detected",
    "edited",
    "deleted",
    "activated",
]

PROCESSING_STATUSES: Final[frozenset[str]] = frozenset(
    {"uploaded", "queued", "parsing", "parsed", "failed"}
)

ALLOWED_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

CHILD_SOURCES: Final[frozenset[str]] = frozenset({"parsed", "manual"})

RESUMES_CONTAINER: Final[str] = "resumes"
SELECTIONS_CONTAINER: Final[str] = "run_resume_selections"
EVENTS_CONTAINER: Final[str] = "resume_parse_events"
VERSIONS_CONTAINER: Final[str] = "resume_versions"

RESUMES_PARTITION_KEY: Final[str] = "/user_id"
SELECTIONS_PARTITION_KEY: Final[str] = "/run_id"
EVENTS_PARTITION_KEY: Final[str] = "/resume_id"
VERSIONS_PARTITION_KEY: Final[str] = "/resume_id"

# Logical Cosmos indexing from the Database PRD.
RESUMES_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [
        {"path": "/*"},
    ],
    "excludedPaths": [
        {"path": "/\"_etag\"/?"},
    ],
    "compositeIndexes": [
        [
            {"path": "/user_id", "order": "ascending"},
            {"path": "/is_deleted", "order": "ascending"},
            {"path": "/updated_at", "order": "descending"},
        ],
        [
            {"path": "/userId", "order": "ascending"},
            {"path": "/updatedAt", "order": "descending"},
        ],
        [{"path": "/createdAt", "order": "ascending"}],
    ],
}

PARSED_TTL_SECONDS: Final[int] = 90 * 86_400

SELECTIONS_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": "/\"_etag\"/?"}],
    "compositeIndexes": [
        [
            {"path": "/user_id", "order": "ascending"},
            {"path": "/created_at", "order": "descending"},
        ]
    ],
}

EVENTS_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": "/\"_etag\"/?"}],
    "compositeIndexes": [
        [
            {"path": "/resume_id", "order": "ascending"},
            {"path": "/created_at", "order": "descending"},
        ]
    ],
}

VERSIONS_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": "/\"_etag\"/?"}],
    "compositeIndexes": [
        [
            {"path": "/resume_id", "order": "ascending"},
            {"path": "/version", "order": "descending"},
        ],
        [
            {"path": "/resume_id", "order": "ascending"},
            {"path": "/is_deleted", "order": "ascending"},
            {"path": "/created_at", "order": "descending"},
        ],
    ],
}

MAX_SKILLS = 200
MAX_EXPERIENCES = 50
MAX_EDUCATIONS = 30
MAX_SKILL_LEN = 100
MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 2000

CANONICAL_SCHEMA_VERSION: Final[str] = "1"
HEURISTIC_SOURCE_VERSION: Final[str] = "heuristic-v1"
AZURE_OPENAI_SOURCE_VERSION: Final[str] = "azure-openai-v1"
# Attempt 1 / 2 / 3 delays before the next parse retry (seconds).
PARSE_BACKOFF_SECONDS: Final[tuple[int, int, int]] = (1, 4, 16)
USER_ACTIVE_RUN_PREFIX: Final[str] = "user:"
