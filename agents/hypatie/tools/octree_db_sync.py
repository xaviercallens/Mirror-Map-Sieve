# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hypatie Supabase DB and Storage Synchronization Client.

Provides direct access for Hypatie to pull/push projects, files, and drafts
directly from/to the octree-agora Supabase backend.
"""

from __future__ import annotations

import os
from typing import Any
import httpx
import structlog

logger = structlog.get_logger(__name__)


class OctreeSyncClient:
    """Synchronizes LaTeX documents and project structures with Supabase."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.supabase_url = supabase_url or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
        self.auth_token = auth_token or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url:
            logger.warning("supabase_url_missing", msg="Supabase URL is not set in environment.")
        if not self.supabase_key:
            logger.warning("supabase_key_missing", msg="Supabase Key is not set in environment.")

    def _get_headers(self, require_auth: bool = True) -> dict[str, str]:
        """Generate headers for Supabase REST and Storage APIs."""
        headers = {
            "apikey": self.supabase_key or "",
        }
        token = self.auth_token
        if require_auth and token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def pull_project_metadata(self, project_id: str) -> dict[str, Any] | None:
        """Fetch project details from projects table."""
        if not self.supabase_url:
            return None

        url = f"{self.supabase_url}/rest/v1/projects"
        params = {"id": f"eq.{project_id}"}
        
        try:
            with httpx.Client() as client:
                res = client.get(url, params=params, headers=self._get_headers())
                res.raise_for_status()
                data = res.json()
                return data[0] if data else None
        except Exception as exc:
            logger.error("pull_project_metadata_failed", project_id=project_id, error=str(exc))
            return None

    def pull_project_files_list(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch files metadata from the files table."""
        if not self.supabase_url:
            return []

        url = f"{self.supabase_url}/rest/v1/files"
        params = {"project_id": f"eq.{project_id}"}

        try:
            with httpx.Client() as client:
                res = client.get(url, params=params, headers=self._get_headers())
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            logger.error("pull_project_files_list_failed", project_id=project_id, error=str(exc))
            return []

    def download_file_content(self, project_id: str, filename: str) -> str | None:
        """Download file content from Supabase Storage."""
        if not self.supabase_url:
            return None

        url = f"{self.supabase_url}/storage/v1/object/authenticated/octree/projects/{project_id}/{filename}"
        
        try:
            with httpx.Client() as client:
                res = client.get(url, headers=self._get_headers())
                res.raise_for_status()
                return res.text
        except Exception as exc:
            logger.error("download_file_content_failed", project_id=project_id, filename=filename, error=str(exc))
            return None

    def upload_file_content(self, project_id: str, filename: str, content: str, content_type: str = "text/x-tex") -> bool:
        """Upload/Overwrite file content in Supabase Storage and update metadata size in DB."""
        if not self.supabase_url:
            return False

        # 1. Upload to Storage
        storage_url = f"{self.supabase_url}/storage/v1/object/octree/projects/{project_id}/{filename}"
        headers = self._get_headers()
        headers["x-upsert"] = "true"
        headers["Content-Type"] = content_type

        try:
            with httpx.Client() as client:
                res = client.post(storage_url, content=content, headers=headers)
                res.raise_for_status()
        except Exception as exc:
            logger.error("upload_file_content_storage_failed", project_id=project_id, filename=filename, error=str(exc))
            return False

        # 2. Update metadata (size) in files table
        db_url = f"{self.supabase_url}/rest/v1/files"
        db_headers = self._get_headers()
        db_headers["Prefer"] = "resolution=merge-duplicates"
        
        params = {
            "project_id": project_id,
            "name": filename,
        }
        
        try:
            # First find if file exists to update or insert
            check_url = f"{db_url}?project_id=eq.{project_id}&name=eq.{filename}"
            with httpx.Client() as client:
                check_res = client.get(check_url, headers=self._get_headers())
                files = check_res.json()
                
                payload = {
                    "project_id": project_id,
                    "name": filename,
                    "size": len(content.encode("utf-8")),
                    "type": content_type,
                }
                
                if files:
                    file_id = files[0]["id"]
                    # Update
                    patch_url = f"{db_url}?id=eq.{file_id}"
                    res = client.patch(patch_url, json=payload, headers=db_headers)
                else:
                    # Insert
                    res = client.post(db_url, json=payload, headers=db_headers)
                res.raise_for_status()
            return True
        except Exception as exc:
            logger.error("upload_file_content_db_failed", project_id=project_id, filename=filename, error=str(exc))
            # Even if DB update fails, storage succeeded
            return True

    def pull_project_workspace(self, project_id: str) -> dict[str, str]:
        """Download all text files in the project workspace.
        
        Returns:
            Dict mapping filename to text content.
        """
        logger.info("pulling_project_workspace_start", project_id=project_id)
        files_list = self.pull_project_files_list(project_id)
        workspace: dict[str, str] = {}
        
        for file_meta in files_list:
            name = file_meta.get("name")
            if not name:
                continue
            # Skip binary files if any
            ext = name.lower().split(".")[-1]
            if ext in ("pdf", "png", "jpg", "jpeg", "gif", "zip", "tar", "gz"):
                continue
                
            content = self.download_file_content(project_id, name)
            if content is not None:
                workspace[name] = content
                
        logger.info("pulling_project_workspace_complete", project_id=project_id, file_count=len(workspace))
        return workspace

    def push_project_workspace(self, project_id: str, workspace: dict[str, str]) -> int:
        """Push a dict of files back to the project workspace.
        
        Returns:
            Number of successfully uploaded files.
        """
        logger.info("pushing_project_workspace_start", project_id=project_id)
        success_count = 0
        
        for filename, content in workspace.items():
            content_type = "text/x-tex" if filename.endswith(".tex") else "text/plain"
            if filename.endswith(".bib"):
                content_type = "text/x-bibtex"
            elif filename.endswith(".cls") or filename.endswith(".sty"):
                content_type = "text/x-tex"
                
            ok = self.upload_file_content(project_id, filename, content, content_type)
            if ok:
                success_count += 1
                
        logger.info("pushing_project_workspace_complete", project_id=project_id, success_count=success_count)
        return success_count
