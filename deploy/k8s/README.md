# Kubernetes Deployment (Advanced)

For GKE deployment, the recommended approach is Cloud Run (see
`deploy/terraform/`). Kubernetes is supported for on-premise or
custom cluster deployments.

## Prerequisites

- GKE cluster with GPU node pool (NVIDIA L4)
- `kubectl` configured
- Container images pushed to Artifact Registry

## Notes

- All deployments **must** use `minReplicas: 0` with KEDA or
  Knative for serverless scaling
- Budget enforcement is application-level (see `agents/common/budget_guard.py`)
- GPU requests should use `nvidia.com/gpu: 1` resource limits

## Recommended Architecture

```
Knative Serving
├── socrates-ksvc (CPU, min=0, max=2)
├── galileo-ksvc  (GPU L4, min=0, max=3)
└── euler-ksvc    (CPU, min=0, max=2)
```

## Patent

US-PAT-PEND-2026-0525
