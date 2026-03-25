#!/bin/bash
set -euo pipefail

# Idempotent infra setup for flashcards generation queue + DLQ + lambda mapping.
# Requires AWS CLI credentials in the target account.

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
QUEUE_NAME="${QUEUE_NAME:-flaschard-generate}"
DLQ_NAME="${DLQ_NAME:-flaschard-generate-dlq}"
WORKER_FUNCTION_NAME="${WORKER_FUNCTION_NAME:-flashcards_generate}"
BATCH_SIZE="${BATCH_SIZE:-1}"
VISIBILITY_TIMEOUT_SECONDS="${VISIBILITY_TIMEOUT_SECONDS:-900}"
MAX_RECEIVE_COUNT="${MAX_RECEIVE_COUNT:-5}"

if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
  echo "ERROR: AWS_ACCOUNT_ID must be set"
  exit 1
fi

export AWS_PAGER=""

echo "[1/6] Ensure DLQ exists: ${DLQ_NAME}"
aws sqs create-queue \
  --queue-name "${DLQ_NAME}" \
  --region "${AWS_REGION}" >/dev/null

DLQ_URL="$(aws sqs get-queue-url --queue-name "${DLQ_NAME}" --region "${AWS_REGION}" --query 'QueueUrl' --output text)"
DLQ_ARN="$(aws sqs get-queue-attributes --queue-url "${DLQ_URL}" --attribute-names QueueArn --region "${AWS_REGION}" --query 'Attributes.QueueArn' --output text)"

echo "[2/6] Ensure primary queue exists: ${QUEUE_NAME}"
# AWS CLI v2 shorthand for --attributes cannot embed JSON for RedrivePolicy (quotes break parsing).
# Create the queue idempotently, then apply attributes via JSON (also updates an existing queue).
aws sqs create-queue \
  --queue-name "${QUEUE_NAME}" \
  --region "${AWS_REGION}" >/dev/null

QUEUE_URL="$(aws sqs get-queue-url --queue-name "${QUEUE_NAME}" --region "${AWS_REGION}" --query 'QueueUrl' --output text)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to build SQS --attributes JSON (RedrivePolicy embedding)"
  exit 1
fi

PRIMARY_QUEUE_ATTRIBUTES_JSON="$(
  VISIBILITY_TIMEOUT_SECONDS="${VISIBILITY_TIMEOUT_SECONDS}" \
    DLQ_ARN="${DLQ_ARN}" \
    MAX_RECEIVE_COUNT="${MAX_RECEIVE_COUNT}" \
    python3 - <<'PY'
import json
import os

visibility = os.environ["VISIBILITY_TIMEOUT_SECONDS"]
dlq_arn = os.environ["DLQ_ARN"]
max_receive = int(os.environ["MAX_RECEIVE_COUNT"])

redrive = json.dumps(
    {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": max_receive},
    separators=(",", ":"),
)
attrs = {"VisibilityTimeout": str(visibility), "RedrivePolicy": redrive}
print(json.dumps(attrs, separators=(",", ":")))
PY
)"

aws sqs set-queue-attributes \
  --queue-url "${QUEUE_URL}" \
  --attributes "${PRIMARY_QUEUE_ATTRIBUTES_JSON}" \
  --region "${AWS_REGION}" >/dev/null

QUEUE_ARN="$(aws sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names QueueArn --region "${AWS_REGION}" --query 'Attributes.QueueArn' --output text)"

echo "[3/6] Ensure event source mapping exists and is enabled"
UUID="$(aws lambda list-event-source-mappings \
  --function-name "${WORKER_FUNCTION_NAME}" \
  --event-source-arn "${QUEUE_ARN}" \
  --region "${AWS_REGION}" \
  --query 'EventSourceMappings[0].UUID' \
  --output text 2>/dev/null || true)"

if [[ -z "${UUID}" || "${UUID}" == "None" ]]; then
  aws lambda create-event-source-mapping \
    --function-name "${WORKER_FUNCTION_NAME}" \
    --event-source-arn "${QUEUE_ARN}" \
    --batch-size "${BATCH_SIZE}" \
    --enabled \
    --region "${AWS_REGION}" >/dev/null
  echo "  Created new event source mapping"
else
  aws lambda update-event-source-mapping \
    --uuid "${UUID}" \
    --batch-size "${BATCH_SIZE}" \
    --enabled \
    --region "${AWS_REGION}" >/dev/null
  echo "  Updated existing event source mapping: ${UUID}"
fi

echo "[4/6] Suggested API runtime env vars"
echo "  FLASHCARDS_GENERATION_QUEUE_URL=${QUEUE_URL}"
echo "  AWS_REGION=${AWS_REGION}"

echo "[5/6] Queue details"
echo "  Queue URL: ${QUEUE_URL}"
echo "  Queue ARN: ${QUEUE_ARN}"
echo "  DLQ URL:   ${DLQ_URL}"
echo "  DLQ ARN:   ${DLQ_ARN}"

echo "[6/6] Next steps"
echo "  1) Deploy lambda/flashcards_generate image (build.sh)"
echo "  2) Ensure API runtime role has sqs:SendMessage on ${QUEUE_ARN}"
echo "  3) Ensure worker role has consume/delete/change visibility on ${QUEUE_ARN} and cloudwatch logs permissions"
