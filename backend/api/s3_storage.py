#!/usr/bin/env python3
"""
S3-Compatible Object Storage Client for Backend Service.
Compatible with Railway S3 / Tigris / AWS S3.
"""

import os
import re
from typing import Optional

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None


class S3BackendStorage:
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        public_url_base: Optional[str] = None,
    ):
        self.endpoint_url = (
            endpoint_url
            or os.getenv("S3_ENDPOINT_URL")
            or os.getenv("AWS_ENDPOINT_URL_S3")
            or "https://t3.storageapi.dev"
        ).rstrip("/")
        self.region_name = (
            region_name
            or os.getenv("S3_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_S3_REGION_NAME")
            or "auto"
        )
        self.bucket_name = (
            bucket_name
            or os.getenv("S3_BUCKET_NAME")
            or os.getenv("AWS_STORAGE_BUCKET_NAME")
            or "resilient-module-m3qmihat"
        )
        self.access_key_id = (
            access_key_id
            or os.getenv("S3_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or ""
        )
        self.secret_access_key = (
            secret_access_key
            or os.getenv("S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or ""
        )
        self.public_url_base = (
            public_url_base
            or os.getenv("S3_PUBLIC_URL")
            or os.getenv("S3_CUSTOM_DOMAIN")
            or ""
        ).rstrip("/")

        self._client = None

    def is_configured(self) -> bool:
        """Returns True if minimum required S3 credentials are present."""
        return bool(self.access_key_id and self.secret_access_key and self.bucket_name)

    def get_client(self):
        """Initializes and returns the boto3 S3 client."""
        if not boto3 or not self.is_configured():
            return None

        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region_name,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(s3={"addressing_style": "path"}),
            )
        return self._client

    def extract_s3_key_from_url(self, image_url: str) -> Optional[str]:
        """Extracts the object key from a full S3 URL."""
        if not image_url:
            return None
        clean_url = image_url.split("?")[0]
        if self.bucket_name and f"/{self.bucket_name}/" in clean_url:
            parts = clean_url.split(f"/{self.bucket_name}/", 1)
            if len(parts) == 2 and parts[1]:
                return parts[1]

        match = re.search(r"(timetables/[^/?#]+\.png)", clean_url)
        if match:
            return match.group(1)

        return None

    def delete_object(self, key: str) -> bool:
        """Deletes an object from S3."""
        client = self.get_client()
        if not client or not key:
            return False
        try:
            client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """Generates a presigned GET URL for an object."""
        client = self.get_client()
        if not client or not key:
            return None
        try:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception:
            return None
