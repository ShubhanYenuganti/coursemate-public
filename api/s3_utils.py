"""
S3 utility helpers for material file storage.
Initializes a boto3 S3 client from environment variables and exposes
presigned URL generation, file existence checks, and deletion.
"""
import os
import boto3
from botocore.exceptions import ClientError

ALLOWED_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/svg+xml',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv',
}

_EXTENSION_MAP = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/svg+xml': 'svg',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'text/csv': 'csv',
}


def _get_client():
    return boto3.client(
        's3',
        region_name=os.environ.get('AWS_REGION'),
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    )


def validate_file_type(file_type: str, allowed_types=None) -> bool:
    """Return True if file_type is in the allowed set."""
    if allowed_types is None:
        allowed_types = ALLOWED_TYPES
    return file_type in allowed_types


def get_file_extension(filename: str) -> str:
    """Return the lowercase file extension (without the dot), or empty string."""
    parts = filename.rsplit('.', 1)
    return parts[1].lower() if len(parts) == 2 else ''


def generate_upload_presigned_url(s3_key: str, file_type: str, max_size: int = 50 * 1024 * 1024):
    """
    Generate a presigned POST for a direct browser-to-S3 upload.
    Returns {'url': ..., 'fields': {...}} or raises on error.
    Expiration: 5 minutes. Max upload size: max_size bytes (default 50 MB).
    """
    client = _get_client()
    bucket = os.environ.get('AWS_S3_BUCKET_NAME')
    response = client.generate_presigned_post(
        Bucket=bucket,
        Key=s3_key,
        Fields={'Content-Type': file_type},
        Conditions=[
            {'Content-Type': file_type},
            ['content-length-range', 1, max_size],
        ],
        ExpiresIn=300,
    )
    return response  # {'url': ..., 'fields': {...}}


def generate_download_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """Generate a presigned GET URL for downloading an object. Default expiry: 1 hour."""
    client = _get_client()
    bucket = os.environ.get('AWS_S3_BUCKET_NAME')
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': s3_key},
        ExpiresIn=expiration,
    )


def verify_file_exists(s3_key: str) -> bool:
    """Return True if the S3 object exists, False otherwise."""
    client = _get_client()
    bucket = os.environ.get('AWS_S3_BUCKET_NAME')
    try:
        client.head_object(Bucket=bucket, Key=s3_key)
        return True
    except ClientError:
        return False


def delete_file(s3_key: str) -> None:
    """Delete an object from S3. Raises on error."""
    client = _get_client()
    bucket = os.environ.get('AWS_S3_BUCKET_NAME')
    client.delete_object(Bucket=bucket, Key=s3_key)
