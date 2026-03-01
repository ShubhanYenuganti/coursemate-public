#!/bin/bash
set -e

# Disable AWS CLI pager so commands don't block on `less`
export AWS_PAGER=""

# ─── Configuration ──────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
REPO_NAME="coursemate-embed-materials"
IMAGE_TAG="latest"
FULL_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

cd "$(dirname "$0")"

echo "=== Building Lambda container image ==="
echo ""

# ─── Step 1: Build the Docker image ────────────────────────────────────────
if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  echo "1. Building Docker image..."
  docker build -t "${REPO_NAME}:${IMAGE_TAG}" .
  echo "   Done."
else
  echo "1. Skipping Docker build (SKIP_BUILD=1)"
fi
echo ""

# ─── Step 2: Create ECR repository (if it doesn't exist) ──────────────────
echo "2. Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" 2>/dev/null \
  || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" \
       --image-scanning-configuration scanOnPush=true
echo "   Done."
echo ""

# ─── Step 3: Authenticate Docker with ECR ──────────────────────────────────
echo "3. Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
echo "   Done."
echo ""

# ─── Step 4: Tag and push ─────────────────────────────────────────────────
echo "4. Pushing image to ECR..."
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${FULL_URI}"
docker push "${FULL_URI}"
echo "   Done."
echo ""

# ─── Summary ───────────────────────────────────────────────────────────────
echo "=== Image pushed successfully ==="
echo ""
echo "Image URI: ${FULL_URI}"
echo ""
echo "To create the Lambda function:"
echo "  aws lambda create-function \\"
echo "    --function-name embed_materials \\"
echo "    --package-type Image \\"
echo "    --code ImageUri=${FULL_URI} \\"
echo "    --role arn:aws:iam::${AWS_ACCOUNT_ID}:role/CoursemateLambda \\"
echo "    --timeout 600 \\"
echo "    --memory-size 2048 \\"
echo "    --environment Variables='{\"AWS_S3_BUCKET_NAME\":\"coursemate-materials\",\"DATABASE_URL\":\"<YOUR_DATABASE_URL>\"}'"
echo ""
echo "To update an existing function:"
echo "  aws lambda update-function-code \\"
echo "    --function-name embed_materials \\"
echo "    --image-uri ${FULL_URI}"
