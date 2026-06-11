# Flashcards Generation Infra Runbook

This runbook provisions the queue topology and mapping for async flashcards generation.

## Prerequisites

- AWS CLI authenticated for target account.
- Lambda worker deployed or deployable at `lambda/flashcards_generate`.
- API runtime + worker runtime env support for:
  - `FLASHCARDS_GENERATION_QUEUE_URL`
  - `AWS_REGION` (or `AWS_DEFAULT_REGION`)
  - `DATABASE_URL`
  - `API_KEY_ENCRYPTION_KEY`

## Provision Queue + DLQ + Mapping

Run:

```bash
cd /Users/shubhan/OneShotCourseMate
chmod +x scripts/infra/setup_flashcards_generation_infra.sh
AWS_ACCOUNT_ID=<your-account-id> \
AWS_REGION=us-east-1 \
WORKER_FUNCTION_NAME=flashcards_generate \
./scripts/infra/setup_flashcards_generation_infra.sh
```

Defaults used by script:

- Queue: `flaschard-generate`
- DLQ: `flaschard-generate-dlq`
- Visibility timeout: `900s`
- Max receive count: `5`
- Mapping batch size: `1`

## IAM Policy Templates

Attach policy docs after replacing placeholders:

- API runtime role policy: `lambda/flashcards_generate/iam/api-send-message-policy.json`
- Worker role policy: `lambda/flashcards_generate/iam/worker-consume-policy.json`

## Deploy Worker

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/flashcards_generate
./build.sh
```

## API Runtime Env

Set at deploy platform level:

- `FLASHCARDS_GENERATION_QUEUE_URL=<queue-url-from-script-output>`
- `AWS_REGION=<region>`

## Verification Checklist

1. Trigger `POST /api/flashcards` with `action=estimate`, then `action=generate`.
2. Confirm API returns quickly with `202` and status `queued` or `generating`.
3. Confirm worker logs show transition `queued -> generating -> ready|failed`.
4. Confirm failed jobs redrive to DLQ after retries.
