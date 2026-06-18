"""Alexandrie Vault — Central knowledge repository for the Agora.

This module implements the storage logic for the Alexandrie Vault,
backing data into Google Cloud Storage (GCS) and metadata into Firestore.
"""

import json
import os
import uuid
import tempfile
import structlog
from typing import Any

logger = structlog.get_logger(__name__)

class AlexandrieVault:
    """Manages long-term memory, checkpoints, and monographs in GCS."""

    def __init__(self, bucket_name: str | None = None):
        self.project_id = os.environ.get("GCP_PROJECT", "gen-lang-client-0625573011")
        self.bucket_name = bucket_name or os.environ.get("AGORA_VAULT_BUCKET", "agora-autoresearch-001-outputs")
        self._client = None
        try:
            from google.cloud import storage
            self._client = storage.Client(project=self.project_id)
            self._bucket = self._client.bucket(self.bucket_name)
        except Exception as e:
            logger.warning("alexandrie_gcs_init_failed", error=str(e))
            self._bucket = None

    def store_json(self, object_name: str, data: dict[str, Any]) -> str:
        """Store a JSON object in the vault."""
        if not self._bucket:
            logger.warning("alexandrie_vault_offline", action="store_json", object=object_name)
            return f"local://{object_name}"

        try:
            blob = self._bucket.blob(object_name)
            blob.upload_from_string(json.dumps(data, ensure_ascii=False), content_type="application/json")
            uri = f"gs://{self.bucket_name}/{object_name}"
            logger.info("alexandrie_stored", uri=uri)
            return uri
        except Exception as e:
            logger.error("alexandrie_store_failed", object=object_name, error=str(e))
            raise

    def load_json(self, object_name: str) -> dict[str, Any]:
        """Load a JSON object from the vault."""
        if not self._bucket:
            logger.warning("alexandrie_vault_offline", action="load_json", object=object_name)
            return {}

        try:
            blob = self._bucket.blob(object_name)
            content = blob.download_as_text()
            return json.loads(content)
        except Exception as e:
            logger.error("alexandrie_load_failed", object=object_name, error=str(e))
            return {}

    def upload_file(self, local_path: str, object_name: str) -> str:
        """Upload a local file to the vault via streaming chunked upload."""
        if not self._bucket:
            logger.warning("alexandrie_vault_offline", action="upload_file", object=object_name)
            return f"local://{object_name}"

        try:
            blob = self._bucket.blob(object_name)
            blob.chunk_size = 5 * 1024 * 1024 # 5 MB chunks
            blob.upload_from_filename(local_path)
            uri = f"gs://{self.bucket_name}/{object_name}"
            logger.info("alexandrie_file_uploaded", uri=uri)
            return uri
        except Exception as e:
            logger.error("alexandrie_upload_failed", object=object_name, error=str(e))
            raise
