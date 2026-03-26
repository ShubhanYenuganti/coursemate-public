#!/bin/bash
set -euo pipefail
export AWS_PAGER=""

AWS_REGION="${AWS_REGION:-us-east-1}"
REPO_NAME="coursemate-reports-generate"
FUNCTION_NAME="reports_generate"
IMAGE_TAG="latest"

cd "$(dirname "$0")"

resolve_aws_account_id() {
  if [[ -n "${AWS_ACCOUNT_ID:-}" ]]; then
    printf '%s\n' "${AWS_ACCOUNT_ID}"
    return 0
  fi

  local derived_account_id
  derived_account_id="$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}" 2>/dev/null || true)"
  if [[ -z "${derived_account_id}" || "${derived_account_id}" == "None" ]]; then
    echo "AWS_ACCOUNT_ID is not set and could not be derived from the current AWS caller identity." >&2
    return 1
  fi

  printf '%s\n' "${derived_account_id}"
}

AWS_ACCOUNT_ID="$(resolve_aws_account_id)"
FULL_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

echo "=== Building Lambda container image ==="

if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  echo "1. Ensuring ECR repository exists..."
  aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" 2>/dev/null \
    || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" \
      --image-scanning-configuration scanOnPush=true
  echo "   Done."

  echo "2. Logging in to ECR..."
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

  echo "3. Building Docker image for linux/amd64..."
  docker buildx build --platform linux/amd64 \
    -t "${REPO_NAME}:${IMAGE_TAG}" \
    -t "${FULL_URI}" \
    --load .

  echo "   Pushing image to ECR..."
  docker push "${FULL_URI}"
else
  echo "1-3. Skipping ECR setup and build (SKIP_BUILD=1)"
fi

echo "4. Deploying Lambda function '${FUNCTION_NAME}'..."
if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
  echo "   Updating existing function code..."
  aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --image-uri "${FULL_URI}" \
    --region "${AWS_REGION}"
else
  echo "   Creating new Lambda function..."
  aws lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --package-type Image \
    --code ImageUri="${FULL_URI}" \
    --role "arn:aws:iam::${AWS_ACCOUNT_ID}:role/CoursemateLambda" \
    --architectures x86_64 \
    --timeout 600 \
    --memory-size 1024 \
    --environment "Variables={DATABASE_URL=<YOUR_DATABASE_URL>,API_KEY_ENCRYPTION_KEY=<YOUR_KEY>}" \
    --region "${AWS_REGION}"
fi
echo "   Done."

echo ""
echo "=== Deployment complete ==="
echo "Image URI: ${FULL_URI}"
echo ""
echo "Next steps:"
echo "1. Set API env var:"
echo "   REPORTS_GENERATION_QUEUE_URL=https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/reports-generate"
echo ""
echo "2. Create event source mapping (if not exists):"
echo "   aws lambda create-event-source-mapping \\" 
echo "     --function-name ${FUNCTION_NAME} \\" 
echo "     --event-source-arn arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:reports-generate \\" 
echo "     --batch-size 1 \\" 
echo "     --enabled \\" 
echo "     --region ${AWS_REGION}"
