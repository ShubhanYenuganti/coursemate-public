#!/bin/bash
set -e

# Disable AWS CLI pager so commands don't block on `less`
export AWS_PAGER=""

# ─── Configuration ──────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
REPO_NAME="coursemate-embed-query"
FUNCTION_NAME="embed_query"
IMAGE_TAG="latest"
FULL_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

cd "$(dirname "$0")"

echo "=== Building Lambda container image ==="
echo ""

if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  # ─── Step 1: Create ECR repository (if it doesn't exist) ──────────────────
  echo "1. Ensuring ECR repository exists..."
  aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" 2>/dev/null \
    || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" \
         --image-scanning-configuration scanOnPush=true
  echo "   Done."
  echo ""

  # ─── Step 2: Authenticate Docker with ECR ─────────────────────────────────
  echo "2. Logging in to ECR..."
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  echo "   Done."
  echo ""

  # ─── Step 3: Build image locally, then push (buildx --push bypasses login) ─
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
  echo "1–3. Skipping ECR setup, login, and build (SKIP_BUILD=1)"
  echo ""
fi

# ─── Step 4: Create or update the Lambda function ───────────────────────────
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
    --timeout 60 \
    --memory-size 1024 \
    --region "${AWS_REGION}"

  echo "   Waiting for function to become active..."
  aws lambda wait function-active --function-name "${FUNCTION_NAME}" --region "${AWS_REGION}"

  echo "   Adding Function URL (auth-type NONE)..."
  aws lambda create-function-url-config \
    --function-name "${FUNCTION_NAME}" \
    --auth-type NONE \
    --region "${AWS_REGION}"

  echo "   Granting public invoke permission for Function URL..."
  aws lambda add-permission \
    --function-name "${FUNCTION_NAME}" \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal '*' \
    --function-url-auth-type NONE \
    --region "${AWS_REGION}"
fi
echo "   Done."
echo ""

# ─── Summary ────────────────────────────────────────────────────────────────
echo "=== Deployment complete ==="
echo ""
FUNCTION_URL=$(aws lambda get-function-url-config \
  --function-name "${FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --query FunctionUrl \
  --output text 2>/dev/null || echo "(Function URL not yet configured)")
echo "Function URL: ${FUNCTION_URL}"
echo ""
echo "Set this in Vercel environment variables:"
echo "  EMBED_QUERY_LAMBDA_URL=${FUNCTION_URL}"
