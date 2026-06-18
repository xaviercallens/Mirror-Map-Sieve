# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# Networking module — IAM service-to-service OIDC bindings for the Agora fleet.
#
# Architecture:
#   - Socrates is the single public-facing entry point (Cloud Run Ingress: ALL)
#   - All other fleet agents are INTERNAL_ONLY (no direct public access)
#   - Only the Agora service account may invoke internal agents via OIDC
#   - Mission Control (Next.js) may invoke Socrates via OIDC
#
# This module wires the OIDC invoker bindings between services.

variable "project_id" { type = string }
variable "region" { type = string }
variable "agora_service_account_email" { type = string }

# ---------------------------------------------------------------------------
# Internal fleet agents — Agora SA can invoke them
# ---------------------------------------------------------------------------

locals {
  internal_agents = [
    "galois-agent",
    "euler-agent",
    "galileo-agent",
    "hypatie-agent",
    "alexandrie-vault",
    "pythagore-agent",
    "heraclite-agent",
    "turing-agent",
  ]
}

resource "google_cloud_run_v2_service_iam_binding" "fleet_invoker" {
  for_each = toset(local.internal_agents)

  project  = var.project_id
  location = var.region
  name     = each.key
  role     = "roles/run.invoker"

  members = [
    "serviceAccount:${var.agora_service_account_email}",
  ]

  # Suppress if the service doesn't exist yet (first-time deploy)
  lifecycle {
    ignore_changes = [members]
  }
}

# ---------------------------------------------------------------------------
# Socrates — accepts traffic from authenticated users + Mission Control SA
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "socrates_public" {
  project  = var.project_id
  location = var.region
  name     = "socrates-agent"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.agora_service_account_email}"
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "internal_agent_names" {
  value = local.internal_agents
}
