# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# Cloud Run module — deploys a serverless container with min_replicas=0
# Security: all services are internal-only; OIDC is required to invoke them.

variable "project_id" { type = string }
variable "region" { type = string }
variable "service_name" { type = string }
variable "container_image" { type = string }
variable "min_replicas" {
  type    = number
  default = 0

  validation {
    condition     = var.min_replicas == 0
    error_message = "Serverless policy: min_replicas must be 0 (scale-to-zero required)."
  }
}
variable "max_replicas" {
  type    = number
  default = 3
}
variable "cpu" {
  type    = string
  default = "2"
}
variable "memory" {
  type    = string
  default = "4Gi"
}
variable "gpu_type" {
  type    = string
  default = ""
}
variable "service_account" { type = string }
variable "env_vars" {
  type    = map(string)
  default = {}
}
variable "invoker_service_account" {
  type        = string
  description = "Service account email allowed to invoke this Cloud Run service via OIDC."
}

variable "ingress" {
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  description = "Ingress traffic configuration. Default is INGRESS_TRAFFIC_INTERNAL_ONLY."
}

variable "args" {
  type        = list(string)
  description = "Arguments (CMD override) to pass to the container."
}

# ---------------------------------------------------------------------------
# Cloud Run v2 Service
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "agent" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  # Ingress traffic configuration
  ingress = var.ingress

  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    timeout               = "3600s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = var.min_replicas  # MUST be 0 — enforced by validation above
      max_instance_count = var.max_replicas
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

    containers {
      image = var.container_image
      args  = var.args

      volume_mounts {
        name       = "secrets-volume"
        mount_path = "/secrets"
      }
      volume_mounts {
        name       = "mistral-volume"
        mount_path = "/secrets/mistral"
      }

      resources {
        limits = merge(
          {
            cpu    = var.cpu
            memory = var.memory
          },
          var.gpu_type != "" ? { "nvidia.com/gpu" = "1" } : {}
        )
        cpu_idle = var.gpu_type != "" ? false : true  # CPU throttling MUST be disabled for GPUs
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Inject the service's own Cloud Run URL for A2A self-advertisement
      env {
        name  = "AGENT_URL"
        value = "https://${var.service_name}-${var.project_id}.${var.region}.run.app"
      }

      ports {
        container_port = 8080
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 30
        period_seconds        = 10
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    service_account = var.service_account

    # node_selector removed (not supported here)

    # Max Cloud Run timeout = 3600s. Required for long MCTS Class 3 proofs.
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    app    = "socrateai-agora"
    agent  = var.service_name
    patent = "us-pat-pend-2026-0525"
  }

  # Lifecycle: prevent Terraform from destroying the service if only traffic changes
  lifecycle {
    ignore_changes = [traffic]
  }
}

# ---------------------------------------------------------------------------
# IAM: Only the Agora service account may invoke this service (OIDC enforced)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_binding" "agent_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agent.name
  role     = "roles/run.invoker"

  members = [
    "serviceAccount:${var.invoker_service_account}",
  ]
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "service_url" {
  value = google_cloud_run_v2_service.agent.uri
}

output "service_name" {
  value = google_cloud_run_v2_service.agent.name
}
