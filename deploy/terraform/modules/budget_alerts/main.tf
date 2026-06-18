# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
#
# Budget alerts module — two-tier budget kill system:
#
# Tier 1 (Python BudgetGuard): soft-kill at $100/experiment, $500/project
#   Raises BudgetExceededError and returns INCOMPLETE_BUDGET status.
#
# Tier 2 (Pub/Sub + Cloud Function): hard infrastructure kill at 85%/$425
#   Publishes a billing alert event to Pub/Sub. Cloud Function receives
#   it and forces all Cloud Run services to max-replicas=0 via gcloud CLI.

variable "project_id" { type = string }
variable "billing_account" { type = string }
variable "budget_amount" {
  type    = number
  default = 500
}
variable "alert_emails" {
  type    = list(string)
  default = []
}
variable "region" {
  type    = string
  default = "us-central1"
}

data "google_project" "project" {
  project_id = var.project_id
}

# ---------------------------------------------------------------------------
# Tier 2 Hard-Kill: Pub/Sub Topic + Cloud Function
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "budget_kill_switch" {
  name    = "agora-budget-kill-switch"
  project = var.project_id
}

resource "google_pubsub_topic_iam_member" "billing_pubsub_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.budget_kill_switch.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:billing-budget-alert@system.gserviceaccount.com"
}

resource "google_storage_bucket" "kill_switch_fn_source" {
  name          = "${var.project_id}-kill-switch-fn"
  location      = var.region
  project       = var.project_id
  force_destroy = true

  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}

# Package the kill switch Cloud Function source
data "archive_file" "kill_switch_source" {
  type        = "zip"
  source_dir  = "${path.module}/kill_switch_function"
  output_path = "${path.module}/kill_switch_function.zip"
}

resource "google_storage_bucket_object" "kill_switch_source" {
  name   = "kill_switch_function_${data.archive_file.kill_switch_source.output_md5}.zip"
  bucket = google_storage_bucket.kill_switch_fn_source.name
  source = data.archive_file.kill_switch_source.output_path
}

resource "google_cloudfunctions2_function" "kill_switch" {
  count = var.billing_account != "" ? 1 : 0

  name     = "agora-budget-kill-switch"
  location = var.region
  project  = var.project_id

  description = "Hard-kills all Agora Cloud Run services when billing budget is exceeded."

  build_config {
    runtime     = "python311"
    entry_point = "kill_switch_handler"

    source {
      storage_source {
        bucket = google_storage_bucket.kill_switch_fn_source.name
        object = google_storage_bucket_object.kill_switch_source.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    min_instance_count = 0
    timeout_seconds    = 60
    available_memory   = "256Mi"

    environment_variables = {
      PROJECT_ID = var.project_id
      REGION     = var.region
    }
  }

  event_trigger {
    event_type   = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic = google_pubsub_topic.budget_kill_switch.id
    retry_policy = "RETRY_POLICY_DO_NOT_RETRY"
  }
}

# ---------------------------------------------------------------------------
# Billing Budget with Pub/Sub routing for hard-kill
# ---------------------------------------------------------------------------

resource "google_billing_budget" "agora_budget" {
  count = var.billing_account != "" ? 1 : 0

  billing_account = var.billing_account
  display_name    = "SocrateAI Agora Budget"

  budget_filter {
    projects = ["projects/${data.google_project.project.number}"]
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(var.budget_amount)
    }
  }

  # Alert at 10% ($50), 20% ($100), 50% ($250), 80% ($400), 100% ($500)
  threshold_rules {
    threshold_percent = 0.10
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.20
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.50
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.80
    spend_basis       = "CURRENT_SPEND"
  }

  # Tier 2 hard-kill trigger at 85% ($425) via Pub/Sub
  threshold_rules {
    threshold_percent = 0.85
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.00
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    # Route billing events to kill-switch Pub/Sub topic for Tier 2 enforcement
    pubsub_topic              = google_pubsub_topic.budget_kill_switch.id
    monitoring_notification_channels = []
    disable_default_iam_recipients = false
  }
}
