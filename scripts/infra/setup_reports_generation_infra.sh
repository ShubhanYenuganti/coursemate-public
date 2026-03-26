#!/bin/bash
# setup_reports_generation_infra.sh
# Sets up event source mapping from SQS reports-generate -> Lambda reports_generate.
# The primary queue reports-generate already exists; this script only adds the mapping.
# Run AFTER deploying lambda/reports_generate via build.sh.
set -euo pipefail
export AWS_PAGER=""

AWS_REGION="${AWS_REGION:-us-east-1}"
QUEUE_NAME="reports-generate"
FUNCTION_NAME="reports_generate"

resolve_aws_account_id() {
  if [[ -n "${AWS_ACCOUNT_ID:-}" ]]; then
    printf '%s\n' "${AWS_ACCOUNT_ID}"
    return 0
  fi

  local derived_account_id
  derived_account_id="$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")"
  if [[ -z "${derived_account_id}" || "${derived_account_id}" == "None" ]]; then
    echo "AWS_ACCOUNT_ID is not set and could not be derived from caller identity." >&2
    return 1
  fi

  printf '%s\n' "${derived_account_id}"
}

AWS_ACCOUNT_ID="$(resolve_aws_account_id)"
QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:${QUEUE_NAME}"

echo "=== Reports Generation Infra Setup ==="
echo "Queue ARN: ${QUEUE_ARN}"
echo "Function:  ${FUNCTION_NAME}"
echo ""

# Check if mapping already exists.
EXISTING="$(aws lambda list-event-source-mappings \
  --function-name "${FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --query "EventSourceMappings[?EventSourceArn=='${QUEUE_ARN}'].UUID" \
  --output text)"

if [[ -n "${EXISTING}" && "${EXISTING}" != "None" ]]; then
  echo "Event source mapping already exists (UUID: ${EXISTING}). Skipping."
else
  echo "Creating event source mapping..."
  aws lambda create-event-source-mapping \
    --function-name "${FUNCTION_NAME}" \
    --event-source-arn "${QUEUE_ARN}" \
    --batch-size 1 \
    --enabled \
    --region "${AWS_REGION}"
  echo "Done."
fi

echo ""
echo "Remember to set on your API runtime:"
echo "  REPORTS_GENERATION_QUEUE_URL=https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/${QUEUE_NAME}"
echo "  AWS_REGION=${AWS_REGION}"
