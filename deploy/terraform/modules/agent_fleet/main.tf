# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# Agent fleet module — deploys all Agora agents as separate Cloud Run services.
# Each agent gets its own service account binding, health check, and scaling.

variable "project_id" { type = string }
variable "region" { type = string }
variable "service_account" { type = string }
variable "budget_limit" {
  type    = number
  default = 100
}
variable "project_budget" {
  type    = number
  default = 200
}
variable "alexandrie_url" {
  type    = string
  default = ""
}
variable "container_registry" {
  type    = string
  default = ""
}

variable "ingress" {
  type    = string
  default = "INGRESS_TRAFFIC_INTERNAL_ONLY"
}

locals {
  registry = var.container_registry != "" ? var.container_registry : "${var.region}-docker.pkg.dev/${var.project_id}/agora"

  # Agent fleet definitions: name → compute profile
  agent_profiles = {
    archimedes = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    aristotle  = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    bourbaki   = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    champollion= { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    curie      = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    descartes  = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    einstein   = { cpu = "8", memory = "16Gi", max_replicas = 2 }
    euler      = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    feynman    = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    galileo    = { cpu = "4", memory = "8Gi",  max_replicas = 2 }
    galois     = { cpu = "8", memory = "16Gi", max_replicas = 4 }
    heraclite  = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    hilbert    = { cpu = "4", memory = "8Gi",  max_replicas = 2 }
    hypatie    = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    lindelof   = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    lovelace   = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    noether    = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    pasteur    = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    pythagore  = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    ramanujan  = { cpu = "8", memory = "16Gi", max_replicas = 2 }
    riemann    = { cpu = "8", memory = "16Gi", max_replicas = 2 }
    socrates   = { cpu = "2", memory = "4Gi",  max_replicas = 2 }
    turing     = { cpu = "2", memory = "8Gi",  max_replicas = 1 }
  }
}

resource "google_cloud_run_v2_service" "fleet_agents" {
  for_each = local.agent_profiles

  name     = "${each.key}-agent"
  location = var.region
  project  = var.project_id

  # Ingress traffic configuration
  ingress = var.ingress

  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    timeout               = "3600s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0  # scale-to-zero enforced
      max_instance_count = each.value.max_replicas
    }

    volumes {
      name = "secrets-volume"
      secret {
        secret = "GEMINI_API_KEY"
        items {
          version = "latest"
          path    = "GEMINI_API_KEY"
        }
      }
    }
    
    volumes {
      name = "mistral-volume"
      secret {
        secret = "GALOIS_MISTRAL_KEY"
        items {
          version = "latest"
          path    = "GALOIS_MISTRAL_KEY"
        }
      }
    }

    service_account = var.service_account

    containers {
      image = "${local.registry}/${each.key}:latest"
      args  = ["agents.${each.key}.server"]

      volume_mounts {
        name       = "secrets-volume"
        mount_path = "/secrets"
      }
      volume_mounts {
        name       = "mistral-volume"
        mount_path = "/secrets/mistral"
      }

      resources {
        limits = {
          cpu    = each.value.cpu
          memory = each.value.memory
        }
        cpu_idle = true
      }

      env {
        name  = "AGENT_NAME"
        value = each.key
      }
      env {
        name  = "AGENT_MODULE"
        value = "agents.${each.key}.server"
      }

      env {
        name  = "BUDGET_LIMIT"
        value = tostring(var.budget_limit)
      }
      env {
        name  = "PROJECT_BUDGET"
        value = tostring(var.project_budget)
      }
      env {
        name  = "ALEXANDRIE_API_URL"
        value = var.alexandrie_url
      }
      env {
        name  = "OIDC_ENABLED"
        value = "1"
      }
      env {
        name  = "FIRESTORE_ENABLED"
        value = "1"
      }

      ports {
        container_port = 8080
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    app    = "socrateai-agora"
    agent  = each.key
    patent = "us-pat-pend-2026-0525"
  }
}

# ---------------------------------------------------------------------------
# IAM: Only Agora service account can invoke fleet agents
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_binding" "fleet_invoker" {
  for_each = local.agent_profiles

  project  = var.project_id
  location = var.region
  name     = "${each.key}-agent"
  role     = "roles/run.invoker"

  members = [
    "serviceAccount:${var.service_account}",
  ]

  depends_on = [google_cloud_run_v2_service.fleet_agents]
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "agent_urls" {
  value = {
    for k, svc in google_cloud_run_v2_service.fleet_agents :
    k => svc.uri
  }
}
