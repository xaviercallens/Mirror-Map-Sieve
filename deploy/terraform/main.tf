# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# Main Terraform configuration for SocrateAI Scientific Agora v4.0.0
# Deploys to GCP with Cloud Run (serverless, min_replicas=0)
# Security: all internal services require OIDC — no public access except Socrates.
#
# Patent: US-PAT-PEND-2026-0525

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }

  backend "gcs" {
    bucket = "socrateai-terraform-state"
    prefix = "agora/state"
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}

provider "google" {
  alias                 = "gpu_region"
  project               = var.project_id
  region                = var.gpu_region
  billing_project       = var.project_id
  user_project_override = true
}

# ---------------------------------------------------------------------------
# Enable required APIs
# ---------------------------------------------------------------------------

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
  ])

  project = var.project_id
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

# ---------------------------------------------------------------------------
# Service Account — single identity for all Agora fleet services
# ---------------------------------------------------------------------------

resource "google_service_account" "agora" {
  account_id   = "socrateai-agora"
  display_name = "SocrateAI Scientific Agora Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "agora_roles" {
  for_each = toset([
    "roles/run.invoker",
    "roles/storage.objectAdmin",
    "roles/monitoring.metricWriter",
    "roles/datastore.user",       # Firestore A2A task state
    "roles/pubsub.publisher",     # Budget kill switch Pub/Sub
    "roles/aiplatform.user",      # Vertex AI endpoint invocation
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.agora.email}"
}

# ---------------------------------------------------------------------------
# Alexandrie Storage Vault (document knowledge base)
# ---------------------------------------------------------------------------

module "alexandrie_storage" {
  source = "./modules/gcs_storage"

  project_id  = var.project_id
  region      = var.region
  bucket_name = "${var.project_id}-alexandrie-vault"
}

module "checkpoint_storage" {
  source = "./modules/gcs_storage"

  project_id  = var.project_id
  region      = var.region
  bucket_name = "${var.project_id}-agora-checkpoints"
}

# ---------------------------------------------------------------------------
# Socrates — single public-facing entry point (accepts external traffic)
# ---------------------------------------------------------------------------

module "socrates_service" {
  source = "./modules/cloud_run"

  project_id              = var.project_id
  region                  = var.region
  service_name            = "socrates-agent"
  container_image         = "${var.region}-docker.pkg.dev/${var.project_id}/agora/socrates:latest"
  min_replicas            = 0
  max_replicas            = 2
  cpu                     = "2"
  memory                  = "4Gi"
  gpu_type                = ""
  service_account         = google_service_account.agora.email
  invoker_service_account = google_service_account.agora.email
  ingress                 = "INGRESS_TRAFFIC_ALL"
  args                    = ["agents.socrates.server"]
  env_vars = {
    AGENT_NAME       = "socrates"
    BUDGET_LIMIT     = tostring(var.budget_limit)
    PROJECT_BUDGET   = tostring(var.project_budget)
    OIDC_ENABLED     = "1"
    FIRESTORE_ENABLED = "1"
  }
}

# ---------------------------------------------------------------------------
# Alexandrie Service (knowledge vault — internal only)
# ---------------------------------------------------------------------------

module "alexandrie_service" {
  source = "./modules/cloud_run"

  project_id              = var.project_id
  region                  = var.region
  service_name            = "alexandrie-vault"
  container_image         = "${var.region}-docker.pkg.dev/${var.project_id}/agora/alexandrie:latest"
  min_replicas            = 0
  max_replicas            = 3
  cpu                     = "2"
  memory                  = "4Gi"
  gpu_type                = ""
  service_account         = google_service_account.agora.email
  invoker_service_account = google_service_account.agora.email
  ingress                 = var.fleet_ingress
  args                    = ["alexandrie.server"]
  env_vars = {
    ALEXANDRIE_VAULT_ROOT = "/gcs/${var.project_id}-alexandrie-vault"
    OIDC_ENABLED          = "1"
  }
}

# ---------------------------------------------------------------------------
# Galileo Service (experimental scientist — GPU optional)
# ---------------------------------------------------------------------------

module "galileo_service" {
  source = "./modules/cloud_run"

  project_id              = var.project_id
  region                  = var.region
  service_name            = "galileo-agent"
  container_image         = "${var.region}-docker.pkg.dev/${var.project_id}/agora/galileo:latest"
  min_replicas            = 0
  max_replicas            = var.gpu_type != "" ? 1 : 3
  cpu                     = "4"
  memory                  = "16Gi"
  gpu_type                = var.gpu_type
  service_account         = google_service_account.agora.email
  invoker_service_account = google_service_account.agora.email
  ingress                 = var.fleet_ingress
  args                    = ["agents.galileo.server"]
  env_vars = {
    AGENT_NAME         = "galileo"
    BUDGET_LIMIT       = tostring(var.budget_limit)
    PROJECT_BUDGET     = tostring(var.project_budget)
    NVIDIA_NIM_API_KEY = var.nvidia_nim_api_key
    OIDC_ENABLED       = "1"
    FIRESTORE_ENABLED  = "1"
  }
}

# ---------------------------------------------------------------------------
# Sentinel Pipeline — Public-facing verification API (Phase 4)
# POST /verify → Bourbaki → Aristotle → Galois+Euler → Descartes|Champollion
# ---------------------------------------------------------------------------

module "sentinel_service" {
  source = "./modules/cloud_run"

  project_id              = var.project_id
  region                  = var.region
  service_name            = "sentinel-pipeline"
  container_image         = "${var.region}-docker.pkg.dev/${var.project_id}/agora/sentinel:latest"
  min_replicas            = 0
  max_replicas            = 5
  cpu                     = "4"
  memory                  = "8Gi"
  gpu_type                = ""
  service_account         = google_service_account.agora.email
  invoker_service_account = google_service_account.agora.email
  ingress                 = "INGRESS_TRAFFIC_ALL"   # Public-facing API
  args                    = ["uvicorn", "agents.sentinel_server:app", "--host", "0.0.0.0", "--port", "8080"]
  env_vars = {
    SENTINEL_MODE          = "api"
    Z3_PATH                = "/usr/bin/z3"
    ALEXANDRIE_URL         = module.alexandrie_service.service_url
    LEAN_COMPILER_ENDPOINT = "https://lean-compiler-${var.project_id}.${var.region}.run.app/compile"
    BUDGET_LIMIT           = tostring(var.budget_limit)
    PROJECT_BUDGET         = tostring(var.project_budget)
    OIDC_ENABLED           = "1"
    FIRESTORE_ENABLED      = "1"
  }

  depends_on = [module.alexandrie_service]
}
# ---------------------------------------------------------------------------
# Agent Fleet Module — Euler, Galois, Hypatie, Pythagore, Heraclite, Turing
# ---------------------------------------------------------------------------

module "agent_fleet" {
  source = "./modules/agent_fleet"

  project_id         = var.project_id
  region             = var.region
  service_account    = google_service_account.agora.email
  budget_limit       = var.budget_limit
  project_budget     = var.project_budget
  alexandrie_url     = module.alexandrie_service.service_url
  container_registry = "${var.region}-docker.pkg.dev/${var.project_id}/agora"
  ingress            = var.fleet_ingress

  depends_on = [module.alexandrie_service]
}

# ---------------------------------------------------------------------------
# GPU Serving (Vertex AI — DeepSeek Prover + Artifact Registry)
# ---------------------------------------------------------------------------

module "gpu_serving" {
  source = "./modules/gpu_serving"

  providers = {
    google = google.gpu_region
  }

  project_id = var.project_id
  region     = var.region
  gpu_region = var.gpu_region
}

# ---------------------------------------------------------------------------
# Networking — IAM OIDC bindings between services
# ---------------------------------------------------------------------------

module "networking" {
  source = "./modules/networking"

  project_id                  = var.project_id
  region                      = var.region
  agora_service_account_email = google_service_account.agora.email

  depends_on = [module.agent_fleet, module.socrates_service]
}

# ---------------------------------------------------------------------------
# Budget Alerts — Two-tier kill system
# ---------------------------------------------------------------------------

module "budget_alerts" {
  source = "./modules/budget_alerts"

  project_id      = var.project_id
  region          = var.region
  billing_account = var.billing_account
  budget_amount   = var.project_budget
  alert_emails    = var.alert_emails
}
