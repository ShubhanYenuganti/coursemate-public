import asyncio
import json
import os

import boto3

from db import get_db, mark_job
from worker import index_document

s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1"))

BUCKET = os.environ["AWS_S3_BUCKET_NAME"]
STATE_MACHINE_ARN = os.environ["INDEX_STATE_MACHINE_ARN"]


def _resolve_material(s3_key: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, course_id, file_type, doc_type, title FROM materials WHERE file_url LIKE %s",
            (f"%{s3_key}%",),
        ).fetchone()


def lambda_handler(event, context):
    if "Records" in event:
        for record in event["Records"]:
            s3_key = record["s3"]["object"]["key"]
            sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps({"s3_key": s3_key, "cursor": 0}),
            )
        return {"status": "launched"}

    s3_key = event.get("s3_key")
    if not s3_key:
        return {"status": "failed", "error": "missing s3_key"}

    row = _resolve_material(s3_key)
    material_id = row["id"] if row else None

    try:
        return _worker(event, context, row)
    except Exception as exc:
        if material_id:
            mark_job(material_id, "failed", error=str(exc))
        return {"status": "failed", "s3_key": s3_key, "error": str(exc)}


def _worker(event: dict, context, row) -> dict:
    s3_key = event["s3_key"]
    if not row:
        return {"status": "done", "s3_key": s3_key, "cursor": 0}

    material_id = row["id"]
    course_id = int(row["course_id"]) if row["course_id"] else None
    file_type = row["file_type"]
    doc_type = row["doc_type"] or "general"
    material_title = row.get("title") or ""

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
