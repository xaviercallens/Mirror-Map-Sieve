# Copyright (c) 2026 Xavier Callens and Socrate AI. All rights reserved.

resource "google_storage_bucket" "runux_checkpoints" {
  name          = "socrateai-runux-math-kernel-checkpoints"
  location      = "US"
  project       = "gen-lang-client-0625573011"
  force_destroy = false

  # Utilizing Standard storage for active reads/writes during optimization
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30 # Auto-delete old checkpoints after 30 days to save costs
    }
    action {
      type = "Delete"
    }
  }
}
