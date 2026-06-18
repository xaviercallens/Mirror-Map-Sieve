#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Archive Redeploy Elements
-------------------------
Packages all scripts, Terraform configurations, visual plots, and artifacts,
and uploads them to the Google Cloud Storage bucket (gs://socrateai-alexandrie-vault/)
to enable full redeployment of Agora.
"""

import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

def main():
    print("Starting packaging of Agora redeployment assets...")
    
    # 1. Define paths
    root_dir = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora")
    artifacts_dir = Path("/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a")
    
    # Create temporary directory for staging
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        staging_dir = temp_path / "agora_redeploy_backup"
        os.makedirs(staging_dir, exist_ok=True)
        
        # 2. Copy folders
        print("Staging deploy/ scripts and Terraform...")
        shutil.copytree(root_dir / "deploy", staging_dir / "deploy", dirs_exist_ok=True)
        
        print("Staging scripts/...")
        shutil.copytree(root_dir / "scripts", staging_dir / "scripts", dirs_exist_ok=True)
        
        print("Staging assets/...")
        shutil.copytree(root_dir / "alexandrie/frontend/public/assets", staging_dir / "assets", dirs_exist_ok=True)
        
        print("Staging conversation artifacts...")
        if artifacts_dir.exists():
            shutil.copytree(artifacts_dir, staging_dir / "conversation_artifacts", dirs_exist_ok=True)
        
        # 3. Create tarball
        tarball_path = root_dir / "agora_redeploy_archive.tar.gz"
        print(f"Creating tarball at {tarball_path}...")
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(staging_dir, arcname="agora_redeploy_backup")
            
        print("Tarball created successfully.")
        
        # 4. Upload to GCS
        gcs_dest = "gs://socrateai-alexandrie-vault/redeploy_agora_backup/agora_redeploy_archive.tar.gz"
        print(f"Uploading to {gcs_dest}...")
        try:
            subprocess.run(
                ["gsutil", "cp", str(tarball_path), gcs_dest],
                check=True
            )
            print("Upload completed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Failed to upload to GCS: {e}")
            raise e
        finally:
            # Clean up local tarball
            if tarball_path.exists():
                os.remove(tarball_path)
                print("Cleaned up local temporary tarball.")

if __name__ == "__main__":
    main()
