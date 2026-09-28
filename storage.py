"""
Cloudflare R2 storage client.

R2 speaks the S3 API, so this is the same boto3 client you'd use for AWS S3 —
only the endpoint_url and credentials differ. Swapping back to real S3 later
(if you ever need AWS-specific features) means changing this file only;
nothing in pin_upload.py or the routers needs to change.

Setup: https://developers.cloudflare.com/r2/api/s3/tokens/
Free tier: 10GB storage, no egress fees, 1M Class A + 10M Class B ops/month.
"""

import os
import uuid

import boto3

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]
# Public bucket URL if you enabled R2's public access / custom domain for it;
# otherwise you'd need presigned GET URLs instead (see get_presigned_url below).
R2_PUBLIC_BASE_URL = os.environ["R2_PUBLIC_BASE_URL"]  # e.g. https://pub-xxxx.r2.dev

_client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)


def upload_image(image_bytes: bytes, filename: str, prefix: str = "") -> str:
    """Uploads bytes under an optional prefix (e.g. 'garments/', 'pins/') and
    returns the public URL to store on the model row (image_url field)."""
    key = f"{prefix}{uuid.uuid4()}-{filename}"
    _client.put_object(Bucket=R2_BUCKET, Key=key, Body=image_bytes)
    return f"{R2_PUBLIC_BASE_URL}/{key}"


def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Use this instead of the public URL above if you'd rather keep the
    bucket private — generates a temporary signed GET URL."""
    return _client.generate_presigned_url(
        "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=expires_in,
    )
