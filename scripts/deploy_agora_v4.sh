#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"

echo "============================================================"
echo "🚀 SocrateAI Agora v4.0 - Cloud-Native Deployment Sequence"
echo "Project: $PROJECT_ID | Region: $REGION"
echo "============================================================"

# 1. Create the Artifact Registry first to break circular dependency
echo "[1/3] Provisioning Artifact Registry repository..."
cd deploy/terraform
terraform init
terraform apply -target=module.gpu_serving.google_artifact_registry_repository.agora -auto-approve -var="project_id=$PROJECT_ID" -var="region=$REGION"
cd ../..

# 2. Build and push Docker images using Cloud Build
echo "[2/3] Building and pushing Agora v4 agent images via Cloud Build..."
gcloud builds submit --config deploy/cloudbuild.yaml . --substitutions=_REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/agora"

# 3. Apply the rest of the Terraform infrastructure
echo "[3/3] Deploying v4 fleet, IAM, and networking via Terraform..."
cd deploy/terraform
terraform apply -auto-approve -var="project_id=$PROJECT_ID" -var="region=$REGION"

echo "✅ Agora v4 Fleet deployment complete!"
