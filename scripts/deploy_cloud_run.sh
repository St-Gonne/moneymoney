#!/usr/bin/env bash
# ==============================================================================
# MoneyMoney (Family Wealth Vault) — Google Cloud Run Deployment Script
# ==============================================================================
set -euo pipefail

# Configuration
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
PROJECT_ID="${GCP_PROJECT_ID:-family-vault-demo}"
REGION="asia-south1"
SERVICE_NAME="moneymoney-backend"
REPO_NAME="moneymoney"
IMAGE_TAG="latest"

echo "======================================================================"
echo "🚀 MoneyMoney Backend Deployment to Google Cloud Run"
echo "======================================================================"
echo "Project : ${PROJECT_ID}"
echo "Region  : ${REGION}"
echo "Service : ${SERVICE_NAME}"
echo "======================================================================"

# 1. Verify gcloud CLI
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: 'gcloud' CLI is not found in PATH."
    echo "Please install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

export CLOUDSDK_METRICS_ENVIRONMENT="datacloud.antigravity"

# 2. Set active GCP project
echo "⚙️ Setting active gcloud project to ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}"

# 3. Enable Required Google Cloud APIs
echo "🔌 Enabling required GCP Services..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    containerregistry.googleapis.com

# 4. Create Artifact Registry Repository if not exists
echo "📦 Ensuring Artifact Registry repository exists in ${REGION}..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" &>/dev/null; then
    echo "Creating Docker repository '${REPO_NAME}'..."
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="MoneyMoney Family Vault Backend Container Images"
fi

# 5. Build and Deploy via Cloud Build
echo "🏗️ Submitting build and deployment to Google Cloud Build..."
gcloud builds submit --config=cloudbuild.yaml .

# 6. Retrieve Service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform=managed --region="${REGION}" --format="value(status.url)")

echo "======================================================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "======================================================================"
echo "Cloud Run Service URL : ${SERVICE_URL}"
echo "Health Check          : ${SERVICE_URL}/health"
echo "API Docs (Swagger)    : ${SERVICE_URL}/docs"
echo "======================================================================"
