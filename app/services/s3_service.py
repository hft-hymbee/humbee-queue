"""
S3 File Service
===============
Handles securely downloading attachment files from AWS S3 directly into memory.
"""

import boto3
from urllib.parse import urlparse

from core.config import settings
from core.logging import get_logger

logger = get_logger("service.s3")


class S3Service:
    """Service to interact with AWS S3."""

    @staticmethod
    def get_client():
        """Get an authenticated boto3 S3 client."""
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            logger.warning("AWS credentials not configured. S3 downloads may fail if running locally without default profile.")

        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
        )

    @staticmethod
    def download_file(s3_url: str) -> dict:
        """
        Download a file from an S3 URL into memory.
        Expects format: s3://bucket-name/path/to/{request_id}_original_filename.pdf

        Returns:
            dict containing "bytes" (the raw file) and "filename" (the cleaned filename).
        """
        if not s3_url.startswith("s3://"):
            raise ValueError(f"Invalid S3 URL. Must start with s3:// (got {s3_url})")

        parsed = urlparse(s3_url)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        # Extract the original filename
        # Upstream microservices upload files with a '{request_id}_' prefix to prevent collisions.
        # We split on the FIRST underscore to strip that prefix and get the pure filename.
        raw_filename = key.split("/")[-1]
        parts = raw_filename.split("_", 1)
        original_filename = parts[1] if len(parts) > 1 else raw_filename

        logger.info(f"Attempting to download {key} from S3 bucket {bucket}")

        try:
            client = S3Service.get_client()
            response = client.get_object(Bucket=bucket, Key=key)
            file_bytes = response["Body"].read()

            logger.info(
                f"Successfully downloaded file from S3",
                extra={
                    "s3_bucket": bucket,
                    "s3_key": key,
                    "original_filename": original_filename,
                    "size_bytes": len(file_bytes),
                },
            )
            
            return {
                "bytes": file_bytes,
                "filename": original_filename
            }

        except Exception as e:
            logger.error(
                f"Failed to download file from S3: {e}",
                extra={"s3_url": s3_url, "error_message": str(e)},
            )
            raise
