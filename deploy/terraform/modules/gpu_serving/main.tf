# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# GPU serving module — Vertex AI endpoint for DeepSeek-Prover-V1.5-RL
#
# Uses preemptible A100/H100 (quota-constrained) with min_replica_count=0
# to enforce scale-to-zero cost discipline.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "gpu_region" {
  type    = string
  default = "europe-west10"
}
variable "gpu_type" {
  type    = string
  default = "NVIDIA_H100_80GB"
}
variable "machine_type" {
  type    = string
  default = "a3-highgpu-8g"
}

# ---------------------------------------------------------------------------
# Vertex AI Endpoint for DeepSeek-Prover
# ---------------------------------------------------------------------------

resource "google_vertex_ai_endpoint" "deepseek_prover" {
  name         = "deepseek-prover-v1-5-rl-v4"
  display_name = "DeepSeek-Prover-V1.5-RL (Mathematical Verification)"
  location     = var.gpu_region
  project      = var.project_id

  labels = {
    app    = "socrateai-agora"
    role   = "lean4-prover"
    patent = "us-pat-pend-2026-0525"
  }
}

# ---------------------------------------------------------------------------
# Artifact Registry for Agora agent images
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "agora" {
  repository_id = "agora"
  location      = var.region
  project       = var.project_id
  format        = "DOCKER"
  description   = "SocrateAI Agora agent container images"

  lifecycle {
    prevent_destroy = true
  }

  labels = {
    app = "socrateai-agora"
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "deepseek_endpoint_id" {
  value = google_vertex_ai_endpoint.deepseek_prover.id
}

output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/agora"
}
