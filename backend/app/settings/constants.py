"""Settings database constants (Database PRD)."""

from typing import Final, Literal

EmailProvider = Literal["microsoft_365"]
ConnectionStatus = Literal["pending", "active", "revoked", "expired", "error"]
EntityType = Literal["user_settings", "email_connections"]

CONNECTION_STATUSES: Final[frozenset[str]] = frozenset(
    {"pending", "active", "revoked", "expired", "error"}
)
KNOWN_PROVIDERS: Final[frozenset[str]] = frozenset({"microsoft_365"})

DEFAULT_MATCH_THRESHOLD: Final[int] = 70
MIN_MATCH_THRESHOLD: Final[int] = 0
MAX_MATCH_THRESHOLD: Final[int] = 100

SETTINGS_CONTAINER: Final[str] = "user_settings"
CONNECTIONS_CONTAINER: Final[str] = "email_connections"
AUDIT_CONTAINER: Final[str] = "settings_audit_log"

SETTINGS_PARTITION_KEY: Final[str] = "/user_id"
CONNECTIONS_PARTITION_KEY: Final[str] = "/user_id"
AUDIT_PARTITION_KEY: Final[str] = "/user_id"

TOKEN_FIELDS: Final[frozenset[str]] = frozenset({"access_token_enc", "refresh_token_enc"})

SETTINGS_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": "/\"_etag\"/?"}],
    "compositeIndexes": [
        [
            {"path": "/user_id", "order": "ascending"},
            {"path": "/updated_at", "order": "descending"},
        ]
    ],
}

CONNECTIONS_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [
        {"path": "/\"_etag\"/?"},
        {"path": "/access_token_enc/?"},
        {"path": "/refresh_token_enc/?"},
    ],
    "compositeIndexes": [
        [
            {"path": "/user_id", "order": "ascending"},
            {"path": "/provider", "order": "ascending"},
        ],
        [
            {"path": "/subscription_expires_at", "order": "ascending"},
        ],
    ],
}

AUDIT_INDEXING_POLICY: Final[dict] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": "/\"_etag\"/?"}],
    "compositeIndexes": [
        [
            {"path": "/user_id", "order": "ascending"},
            {"path": "/created_at", "order": "descending"},
        ],
        [
            {"path": "/entity_id", "order": "ascending"},
            {"path": "/created_at", "order": "descending"},
        ],
    ],
}
