#!/bin/bash
set -e

# Disable AWS CLI pager so commands do not block on less.
export AWS_PAGER=""

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
REPO_NAME="coursemate-flashcards-generate"
FUNCTION_NAME="flashcards_generate"
IMAGE_TAG="latest"
FULL_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

cd "$(dirname "$0")"

echo "=== Building Lambda container image ==="
echo ""

if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  echo "1. Ensuring ECR repository exists..."
  aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" 2>/dev/null \
    || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" \
         --image-scanning-configuration scanOnPush=true
  echo "   Done."
  echo ""

  echo "2. Logging in to ECR..."
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  echo "   Done."
  echo ""

  echo "3. Building Docker image for linux/amd64..."
  docker buildx build --platform linux/amd64 \
    -t "${REPO_NAME}:${IMAGE_TAG}" \
    -t "${FULL_URI}" \
    --load .

  echo "   Pushing image to ECR..."
  docker push "${FULL_URI}"
  echo "   Done."
  echo ""
else
  echo "1-3. Skipping ECR setup, login, and build (SKIP_BUILD=1)"
  echo ""
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
echo ""
echo "Image URI: ${FULL_URI}"
echo ""
echo "Next: attach SQS trigger to Lambda '${FUNCTION_NAME}' (queue: flashcards-generate)."
echo "Example:"
echo "  aws lambda create-event-source-mapping \\"
echo "    --function-name ${FUNCTION_NAME} \\"
echo "    --event-source-arn arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:flashcards-generate \\"
echo "    --batch-size 1 \\"
echo "    --enabled \\"
echo "    --region ${AWS_REGION}"
echo ""
echo "Remember to set API env var:"
echo "  FLASHCARDS_GENERATION_QUEUE_URL=https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/flashcards-generate"
