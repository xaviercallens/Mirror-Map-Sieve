# GCP Secret Manager Module for Agora

variable "project_id" {
  description = "The GCP project ID"
  type        = string
  default     = "gen-lang-client-0625573011"
}

# GEMINI_API_KEY
resource "google_secret_manager_secret" "gemini_key" {
  secret_id = "GEMINI_API_KEY"
  project   = var.project_id
  replication {
    auto {}
  }
}

# GALOIS_MISTRAL_KEY
resource "google_secret_manager_secret" "mistral_key" {
  secret_id = "GALOIS_MISTRAL_KEY"
  project   = var.project_id
  replication {
    auto {}
  }
}

# HF_TOKEN
resource "google_secret_manager_secret" "hf_token" {
  secret_id = "HF_TOKEN"
  project   = var.project_id
  replication {
    auto {}
  }
}

# ZENODO_API_KEY
resource "google_secret_manager_secret" "zenodo_key" {
  secret_id = "ZENODO_API_KEY"
  project   = var.project_id
  replication {
    auto {}
  }
}

# NIM_API_KEY
resource "google_secret_manager_secret" "nim_key" {
  secret_id = "NIM_API_KEY"
  project   = var.project_id
  replication {
    auto {}
  }
}

output "gemini_key_id" {
  value = google_secret_manager_secret.gemini_key.secret_id
}

output "mistral_key_id" {
  value = google_secret_manager_secret.mistral_key.secret_id
}

output "hf_token_id" {
  value = google_secret_manager_secret.hf_token.secret_id
}

output "zenodo_key_id" {
  value = google_secret_manager_secret.zenodo_key.secret_id
}

output "nim_key_id" {
  value = google_secret_manager_secret.nim_key.secret_id
}
