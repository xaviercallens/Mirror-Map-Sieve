# Copyright (c) 2026 Xavier Callens and Socrate AI. All rights reserved.
# Terraform for highly cost-optimized Cloud Run Service (Rust Math Kernel API Gateway)

resource "google_cloud_run_v2_service" "runux_math_kernel" {
  name     = "runux-math-kernel-service"
  location = "us-central1"
  project  = "gen-lang-client-0625573011"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "us-central1-docker.pkg.dev/gen-lang-client-0625573011/agora-repo/runux-math-kernel:latest"
      
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      ports {
        container_port = 8080
      }
    }
    
    timeout = "3600s"
    max_instance_request_concurrency = 50
    scaling {
      max_instance_count = 5
      min_instance_count = 0
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

resource "google_cloud_run_service_iam_member" "noauth" {
  service  = google_cloud_run_v2_service.runux_math_kernel.name
  location = google_cloud_run_v2_service.runux_math_kernel.location
  project  = google_cloud_run_v2_service.runux_math_kernel.project
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "api_gateway_url" {
  value = google_cloud_run_v2_service.runux_math_kernel.uri
}
