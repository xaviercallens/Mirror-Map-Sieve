#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Archive Full Repository
-----------------------
Packages the entire workspace repository (excluding git/build/cache folders)
and uploads it to Google Cloud Storage under `gs://socrateai-alexandrie-vault/redeploy_agora_backup/`.
"""

import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

def main():
    print("Starting packaging of full Agora codebase and submodules...")
    
    root_dir = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora")
    gcs_dest = "gs://socrateai-alexandrie-vault/redeploy_agora_backup/agora_full_codebase_backup.tar.gz"
    
    # Exclude directories
    exclude_dirs = {
        ".git",
        ".venv",
        ".lake",
        "node_modules",
        "target",
        "__pycache__",
        ".pytest_cache",
        ".benchmarks",
        "dist",
        "build"
    }
    
    def filter_tar(tarinfo):
        # Check if any part of the path is in exclude_dirs
        path_parts = Path(tarinfo.name).parts
        for part in path_parts:
            if part in exclude_dirs:
                return None
        return tarinfo

    # Create temporary tarball
    tarball_path = root_dir / "agora_full_codebase_backup.tar.gz"
    print(f"Creating full code archive at {tarball_path}...")
    
    try:
        with tarfile.open(tarball_path, "w:gz") as tar:
            # Add the entire root directory with filter
            tar.add(root_dir, arcname="SocrateAI-Scientific-Agora", filter=filter_tar)
            
        print("Archive created successfully. Uploading to GCS...")
        
        # Upload using gsutil
        subprocess.run(
            ["gsutil", "cp", str(tarball_path), gcs_dest],
            check=True
        )
        print(f"Successfully uploaded full codebase to {gcs_dest}!")
        
    except Exception as e:
        print(f"Error occurred during backup: {e}")
        raise e
    finally:
        # Clean up local tarball
        if tarball_path.exists():
            os.remove(tarball_path)
            print("Cleaned up local temporary full codebase tarball.")

if __name__ == "__main__":
    main()
