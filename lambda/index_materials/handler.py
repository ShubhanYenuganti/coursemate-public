import asyncio
import hashlib
import json
import os

import boto3

from db import get_db, mark_job
from worker import index_document

s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1"))

BUCKET = os.environ["AWS_S3_BUCKET_NAME"]
STATE_MACHINE_ARN = os.environ["INDEX_STATE_MACHINE_ARN"]


def _execution_name(s3_key: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in s3_key)[:60]
    suffix = hashlib.md5(s3_key.encode()).hexdigest()[:8]
    return f"{safe}-{suffix}"


def _resolve_material(s3_key: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, course_id, file_type, doc_type, name FROM materials WHERE file_url LIKE %s",
            (f"%{s3_key}%",),
        ).fetchone()


def lambda_handler(event, context):
    if "Records" in event:
        for record in event["Records"]:
            s3_key = record["s3"]["object"]["key"]
            try:
                sfn.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=_execution_name(s3_key),
                    input=json.dumps({"s3_key": s3_key, "cursor": 0}),
                )
            except sfn.exceptions.ExecutionAlreadyExists:
                pass
        return {"status": "launched"}

    s3_key = event.get("s3_key")
    if not s3_key:
        return {"status": "failed", "error": "missing s3_key"}

    # Step Functions Catch routes hard failures (timeout / OOM / unhandled error)
    # here so the job reaches a terminal DB state instead of being frozen at
    # 'processing'. The original worker invocation never got to write a status.
    if event.get("mark_failed"):
        row = _resolve_material(s3_key)
        if row:
            mark_job(row["id"], "failed",
                     error=str(event.get("error", "indexing failed"))[:1000])
        return {"status": "marked_failed", "s3_key": s3_key}

    row = _resolve_material(s3_key)
    material_id = row["id"] if row else None

    try:
        return _worker(event, context, row)
    except Exception as exc:
        if material_id:
            mark_job(material_id, "failed", error=str(exc))
        return {"status": "failed", "s3_key": s3_key, "cursor": 0, "error": str(exc)}


def _worker(event: dict, context, row) -> dict:
    import time
    s3_key = event["s3_key"]
    if not row:
        # S3 trigger may have fired before confirm_upload wrote the material row.
        # Retry for up to 30s so the race resolves without losing the job.
        for _ in range(6):
            time.sleep(5)
            row = _resolve_material(s3_key)
            if row:
                break
    if not row:
        return {"status": "done", "s3_key": s3_key, "cursor": 0}

    material_id = row["id"]
    course_id = int(row["course_id"]) if row["course_id"] else None
    file_type = row["file_type"]
    doc_type = row["doc_type"] or "general"
    material_title = row.get("name") or ""

    if file_type != "application/pdf":
        mark_job(material_id, "skipped", error=f"Non-PDF not supported: {file_type!r}")
        return {"status": "done", "s3_key": s3_key, "cursor": 0}

    mark_job(material_id, "processing")

    obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
    file_bytes = obj["Body"].read()

    asyncio.run(
        index_document(
            material_id=material_id,
            course_id=course_id,
            s3_key=s3_key,
            doc_type=doc_type,
            material_title=material_title,
            file_bytes=file_bytes,
        )
    )

    mark_job(material_id, "done")
    return {"status": "done", "s3_key": s3_key, "cursor": 0}
