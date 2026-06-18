# Copyright (c) 2026 Xavier Callens and Socrate AI. All rights reserved.
# Terraform for the Alien Mathematics Autoresearch Cloud Run Job

resource "google_storage_bucket" "alien_math_archive" {
  name          = "socrateai-alien-math-archive"
  location      = "US"
  project       = "gen-lang-client-0625573011"
  force_destroy = false

  storage_class = "STANDARD"
  uniform_bucket_level_access = true
}

resource "google_cloud_run_v2_job" "alien_math_autoresearcher" {
  name     = "alien-math-autoresearcher"
  location = "us-central1"
  project  = "gen-lang-client-0625573011"

  template {
    template {
      containers {
        # Using the same Artifact Registry but we will tag the python runner as autoresearcher
        image = "us-central1-docker.pkg.dev/gen-lang-client-0625573011/agora-repo/alien-math-autoresearcher:latest"
        
        resources {
          limits = {
            cpu    = "2"
            memory = "1024Mi"
          }
        }
      }
      
      # Strict 1-hour timeout to enforce $50 budget
      timeout = "3600s"
      max_retries = 0
    }

    # Only run 1 task at a time, completely serially
    task_count = 1
    parallelism = 1
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}
