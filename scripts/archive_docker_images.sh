#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/agora"
BUCKET="gs://${PROJECT_ID}-agora-checkpoints/docker-archives"

echo "============================================================"
echo "📦 Archiving Agora Docker Images to GCS Private Storage"
echo "Registry: $REGISTRY"
echo "Destination: $BUCKET"
echo "============================================================"

# List of base images to archive
IMAGES=("agora-base:latest" "sentinel:latest")

for IMAGE in "${IMAGES[@]}"; do
    FULL_IMAGE="${REGISTRY}/${IMAGE}"
    ARCHIVE_NAME=$(echo "${IMAGE}" | tr ':' '-')
    TAR_FILE="/tmp/${ARCHIVE_NAME}.tar.gz"

    echo "🔄 Pulling ${FULL_IMAGE}..."
    docker pull "${FULL_IMAGE}"

    echo "💾 Saving to ${TAR_FILE}..."
    docker save "${FULL_IMAGE}" | gzip > "${TAR_FILE}"

    echo "☁️ Uploading to ${BUCKET}/${ARCHIVE_NAME}.tar.gz..."
    gsutil cp "${TAR_FILE}" "${BUCKET}/${ARCHIVE_NAME}.tar.gz"

    echo "🗑️ Cleaning up local archive..."
    rm "${TAR_FILE}"
    echo "✅ Successfully archived ${IMAGE}"
done

echo "🎉 All images successfully archived to GCS!"
