# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# GCS bucket module for checkpoint storage

variable "project_id" { type = string }
variable "region" { type = string }
variable "bucket_name" { type = string }

resource "google_storage_bucket" "checkpoints" {
  name          = var.bucket_name
  location      = var.region
  project       = var.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  lifecycle_rule {
    condition {
      age = 90  # Delete old checkpoints after 90 days
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    app    = "socrateai-agora"
    patent = "us-pat-pend-2026-0525"
  }
}

output "bucket_name" {
  value = google_storage_bucket.checkpoints.name
}

output "bucket_url" {
  value = google_storage_bucket.checkpoints.url
}
