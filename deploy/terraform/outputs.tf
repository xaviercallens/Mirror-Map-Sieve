# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file

output "socrates_url" {
  description = "Socrates agent Cloud Run URL"
  value       = module.socrates_service.service_url
}

output "galileo_url" {
  description = "Galileo agent Cloud Run URL"
  value       = module.galileo_service.service_url
}

output "euler_url" {
  description = "Euler agent Cloud Run URL"
  value       = module.agent_fleet.agent_urls["euler"]
}

output "galois_url" {
  description = "Galois agent Cloud Run URL"
  value       = module.agent_fleet.agent_urls["galois"]
}

output "hypatie_url" {
  description = "Hypatie agent Cloud Run URL"
  value       = module.agent_fleet.agent_urls["hypatie"]
}

output "alexandrie_url" {
  description = "Alexandrie Storage Hub Cloud Run URL"
  value       = module.alexandrie_service.service_url
}

output "sentinel_url" {
  description = "Sentinel Pipeline API URL (POST /verify)"
  value       = module.sentinel_service.service_url
}

output "checkpoint_bucket" {
  description = "GCS bucket for model checkpoints"
  value       = module.checkpoint_storage.bucket_name
}

output "alexandrie_bucket" {
  description = "GCS bucket for Alexandrie scientific vault storage"
  value       = module.alexandrie_storage.bucket_name
}

