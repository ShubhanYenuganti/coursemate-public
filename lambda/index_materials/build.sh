#!/bin/bash
set -e

# Disable AWS CLI pager so commands don't block on `less`
export AWS_PAGER=""

# ─── Configuration ──────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
REPO_NAME="coursemate-index-materials"
FUNCTION_NAME="index_materials"
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

# ─── Step 4: Create or update the Lambda function ───────────────────────────
echo "4. Deploying Lambda function '${FUNCTION_NAME}'..."
if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
  echo "   Updating existing function code..."
  aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --image-uri "${FULL_URI}" \
    --region "${AWS_REGION}"
  echo "   Waiting for update to complete..."
  aws lambda wait function-updated \
    --function-name "${FUNCTION_NAME}" \
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
    --memory-size 2048 \
    --environment "Variables={AWS_S3_BUCKET_NAME=coursemate-materials,DATABASE_URL=PLACEHOLDER,INDEX_STATE_MACHINE_ARN=PLACEHOLDER,OPENAI_API_KEY_INDEXER=PLACEHOLDER}" \
    --region "${AWS_REGION}"
  echo "   Waiting for function to become active..."
  aws lambda wait function-active \
    --function-name "${FUNCTION_NAME}" \
    --region "${AWS_REGION}"
fi
echo "   Done."
echo ""

# ─── Summary ────────────────────────────────────────────────────────────────
echo "=== Deployment complete ==="
echo ""
echo "Image URI: ${FULL_URI}"
echo ""
echo "Next steps (one-time setup):"
echo ""
echo "1. Create the Step Functions state machine from state_machine.json:"
echo "   aws stepfunctions create-state-machine \\"
echo "     --name index-materials \\"
echo "     --definition file://state_machine.json \\"
echo "     --role-arn arn:aws:iam::${AWS_ACCOUNT_ID}:role/CoursemateLambda \\"
echo "     --region ${AWS_REGION}"
echo ""
echo "2. Update INDEX_STATE_MACHINE_ARN once the state machine is created:"
echo "   aws lambda update-function-configuration \\"
echo "     --function-name ${FUNCTION_NAME} \\"
echo "     --environment 'Variables={AWS_S3_BUCKET_NAME=coursemate-materials,DATABASE_URL=<YOUR_DATABASE_URL>,INDEX_STATE_MACHINE_ARN=arn:aws:states:${AWS_REGION}:${AWS_ACCOUNT_ID}:stateMachine:index-materials,OPENAI_API_KEY_INDEXER=<YOUR_KEY>}' \\"
echo "     --region ${AWS_REGION}"
echo ""
echo "3. Grant S3 permission to invoke the Lambda:"
echo "   aws lambda add-permission \\"
echo "     --function-name ${FUNCTION_NAME} \\"
echo "     --statement-id s3-invoke \\"
echo "     --action lambda:InvokeFunction \\"
echo "     --principal s3.amazonaws.com \\"
echo "     --source-arn arn:aws:s3:::coursemate-materials \\"
echo "     --region ${AWS_REGION}"
echo ""
echo "   Then configure the S3 bucket notification in the console (or via"
echo "   aws s3api put-bucket-notification-configuration) to fire on object"
echo "   creation events targeting this Lambda."
