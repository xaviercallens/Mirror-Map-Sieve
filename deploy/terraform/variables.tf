# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for deployment"
  type        = string
  default     = "us-central1"
}

variable "gpu_region" {
  description = "GCP region for heavy GPU serving (Vertex AI)"
  type        = string
  default     = "us-central1"
}


variable "budget_limit" {
  description = "Per-experiment budget limit in USD"
  type        = number
  default     = 100

  validation {
    condition     = var.budget_limit <= 100
    error_message = "Experiment budget must not exceed $100."
  }
}

variable "project_budget" {
  description = "Total project budget in USD"
  type        = number
  default     = 500

  validation {
    condition     = var.project_budget <= 500
    error_message = "Project budget must not exceed $500."
  }
}

variable "gpu_type" {
  description = "GPU accelerator type for Galileo (L4 recommended, but omitted by default due to Cloud Run redundancy quota constraints)"
  type        = string
  default     = ""
}

variable "billing_account" {
  description = "GCP billing account ID"
  type        = string
  default     = ""
}

variable "nvidia_nim_api_key" {
  description = "NVIDIA NIM API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "alert_emails" {
  description = "Email addresses for budget alerts"
  type        = list(string)
  default     = ["callensxavier@gmail.com"]
}

variable "fleet_ingress" {
  description = "Ingress settings for the agent fleet. Default is INGRESS_TRAFFIC_INTERNAL_ONLY."
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_ONLY"
}
