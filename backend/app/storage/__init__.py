"""Storage client seams for Cosmos DB, Blob Storage, and Storage Queues."""

from app.storage.blob_layout import blob_container_names, lifecycle_rules
from app.storage.catalog import container_catalog, core_container_ids, ensure_all_containers
from app.storage.dal import CosmosDAL, Page
from app.storage.entities import CORE_ENTITIES
from app.storage.provision import connection_info, provision_all
from app.storage.queue_schemas import parse_queue_message, queue_names
from app.storage.dao import domain_daos, ensure_mvp_containers, seed_dao_defaults
from app.storage.seeds import apply_seed, seed_documents

__all__ = [
    "CORE_ENTITIES",
    "CosmosDAL",
    "Page",
    "apply_seed",
    "blob_container_names",
    "connection_info",
    "container_catalog",
    "core_container_ids",
    "domain_daos",
    "ensure_all_containers",
    "ensure_mvp_containers",
    "lifecycle_rules",
    "parse_queue_message",
    "provision_all",
    "queue_names",
    "seed_dao_defaults",
    "seed_documents",
]
