#!/bin/bash
set -e

# Disable AWS CLI pager so commands don't block on `less`
export AWS_PAGER=""

# ─── Configuration ──────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
REPO_NAME="coursemate-integration-poller"
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

  # ─── Step 3: Build image locally, then push ───────────────────────────────
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

# ─── Step 4: Create or update Lambda function ─────────────────────────────
echo "4. Creating or updating Lambda function..."
if aws lambda get-function --function-name integration_poller --region "${AWS_REGION}" 2>/dev/null; then
  echo "   Function exists — updating image..."
  aws lambda update-function-code \
    --function-name integration_poller \
    --image-uri "${FULL_URI}" \
    --region "${AWS_REGION}"
  echo "   Waiting for update to complete..."
  aws lambda wait function-updated \
    --function-name integration_poller \
    --region "${AWS_REGION}"
else
  echo "   Function not found — creating with placeholder env vars (update in Lambda console)..."
  aws lambda create-function \
    --function-name integration_poller \
    --package-type Image \
    --code "ImageUri=${FULL_URI}" \
    --role "arn:aws:iam::${AWS_ACCOUNT_ID}:role/CoursemateLambda" \
    --architectures x86_64 \
    --timeout 600 \
    --memory-size 1024 \
    --region "${AWS_REGION}" \
    --environment 'Variables={AWS_S3_BUCKET_NAME=coursemate-materials,DATABASE_URL=PLACEHOLDER,STATE_MACHINE_ARN=PLACEHOLDER,FERNET_KEY=PLACEHOLDER,GDRIVE_CLIENT_ID=PLACEHOLDER,GDRIVE_CLIENT_SECRET=PLACEHOLDER}'
  echo "   Waiting for function to become active..."
  aws lambda wait function-active \
    --function-name integration_poller \
    --region "${AWS_REGION}"
fi
echo "   Done."
echo ""

# ─── Step 5: Update env vars (GDRIVE credentials) ────────────────────────
echo "5. Updating Lambda environment variables with GDRIVE credentials..."
if [[ -n "${GDRIVE_CLIENT_ID:-}" && -n "${GDRIVE_CLIENT_SECRET:-}" ]]; then
  # Fetch current env vars and merge with GDRIVE additions
  CURRENT_VARS=$(aws lambda get-function-configuration \
    --function-name integration_poller --region "${AWS_REGION}" \
    --query 'Environment.Variables' --output json 2>/dev/null || echo '{}')
  UPDATED_VARS=$(echo "${CURRENT_VARS}" | \
    python3 -c "import json,sys; d=json.load(sys.stdin); d.update({'GDRIVE_CLIENT_ID':'${GDRIVE_CLIENT_ID}','GDRIVE_CLIENT_SECRET':'${GDRIVE_CLIENT_SECRET}'}); print(json.dumps({'Variables':d}))")
  aws lambda update-function-configuration \
    --function-name integration_poller \
    --environment "${UPDATED_VARS}" \
    --region "${AWS_REGION}"
  echo "   GDRIVE credentials set."
else
  echo "   GDRIVE_CLIENT_ID / GDRIVE_CLIENT_SECRET not set in shell — skipping. Set them in Lambda console."
fi
echo ""

# ─── Step 6: Create EventBridge Scheduler rule (if it doesn't exist) ───────
echo "6. Ensuring EventBridge Scheduler rule exists..."
if ! aws scheduler get-schedule --name integration-poller-2h --region "${AWS_REGION}" 2>/dev/null; then
  aws scheduler create-schedule \
    --name integration-poller-2h \
    --schedule-expression 'rate(2 hours)' \
    --flexible-time-window '{"Mode":"OFF"}' \
    --region "${AWS_REGION}" \
    --target "{\"Arn\":\"arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:integration_poller\",\"RoleArn\":\"arn:aws:iam::${AWS_ACCOUNT_ID}:role/CoursemateLambda\",\"Input\":\"{}\"}"
  echo "   Scheduler rule created."
else
  echo "   Scheduler rule already exists — skipping."
fi
echo "   Done."
echo ""

# ─── Summary ─────────────────────────────────────────────────────────────
echo "=== Lambda deployed successfully ==="
echo ""
echo "Image URI: ${FULL_URI}"
