#!/usr/bin/env python3
"""
S3-Compatible Object Storage Client for Timetable Service.
Compatible with Railway S3 / Tigris / AWS S3 / Cloudflare R2.

Features:
  - Uploads group timetable screenshot to S3 bucket.
  - Automatically deletes old timetable screenshot from S3 when updating.
  - Generates public or presigned S3 URLs for frontend & bot usage.
  - Graceful local fallback if S3 credentials are not yet configured.
"""

import os
import re
import time
import urllib.parse
from typing import Optional

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None


class S3StorageManager:
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
            or os.getenv("ACCESS_KEY_ID")
            or os.getenv("TIGRIS_ACCESS_KEY_ID")
            or "tid_sJKHMdAQGSDbJgIZUOoZltQsaWuUlbGaundBPOmwCdvQIJjMfJ"
        ).strip()
        self.secret_access_key = (
            secret_access_key
            or os.getenv("S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("SECRET_ACCESS_KEY")
            or os.getenv("S3_SECRET_KEY")
            or os.getenv("AWS_SECRET_KEY")
            or os.getenv("TIGRIS_SECRET_ACCESS_KEY")
            or os.getenv("S3_SECRET")
            or ""
        ).strip()
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

    def get_public_url(self, group_name: str, key: Optional[str] = None) -> str:
        """Returns the public S3 URL for a group screenshot."""
        if not key:
            sanitized_grp = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name).strip("._") or "group"
            key = f"timetables/{sanitized_grp}.png"
        if self.public_url_base:
            return f"{self.public_url_base}/{key}"
        return f"{self.endpoint_url}/{self.bucket_name}/{key}"

    def get_client(self):
        """Initializes and returns the boto3 S3 client."""
        if not boto3:
            return None
        if not self.is_configured():
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
        """
        Extracts the object key from a full S3 URL or partial path.
        Example: https://t3.storageapi.dev/my-bucket/timetables/CIE26-1.png -> timetables/CIE26-1.png
        """
        if not image_url:
            return None

        # Strip URL query parameters
        clean_url = image_url.split("?")[0]

        # Check if it contains bucket name in path: .../{bucket}/{key}
        if self.bucket_name and f"/{self.bucket_name}/" in clean_url:
            parts = clean_url.split(f"/{self.bucket_name}/", 1)
            if len(parts) == 2 and parts[1]:
                return parts[1]

        # Check if it starts with timetables/
        match = re.search(r"(timetables/[^/?#]+\.png)", clean_url)
        if match:
            return match.group(1)

        # If it looks like a direct key
        if clean_url.startswith("timetables/"):
            return clean_url

        return None

    def delete_object(self, key: str) -> bool:
        """Deletes an object from the S3 bucket by its key."""
        client = self.get_client()
        if not client or not key:
            return False

        try:
            client.delete_object(Bucket=self.bucket_name, Key=key)
            print(f"  [S3] Deleted old timetable image: {key}")
            return True
        except Exception as exc:
            print(f"  [S3 Warning] Failed to delete old object '{key}': {exc}")
            return False

    def upload_timetable_screenshot(
        self,
        group_name: str,
        local_filepath: str,
        old_image_url: Optional[str] = None,
        use_timestamp: bool = True,
    ) -> Optional[str]:
        """
        1. Deletes old timetable photo from S3 (if old_image_url was on S3).
        2. Uploads the new screenshot to S3.
        3. Returns the S3 bucket URL.
        """
        sanitized_grp = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name).strip("._") or "group"
        standard_s3_url = self.get_public_url(group_name)

        if not os.path.exists(local_filepath):
            print(f"  [S3 Error] File does not exist: {local_filepath}")
            return standard_s3_url

        client = self.get_client()
        if not client:
            print(f"  [S3 Info] S3 secret key not yet configured in environment. Linking S3 URL: {standard_s3_url}")
            return standard_s3_url

        # 1. Remove old photo if exists
        if old_image_url:
            old_key = self.extract_s3_key_from_url(old_image_url)
            if old_key:
                self.delete_object(old_key)

        # 2. Upload both permanent key timetables/{group}.png and versioned key
        timestamp = int(time.time())
        main_key = f"timetables/{sanitized_grp}.png"
        versioned_key = f"timetables/{sanitized_grp}_{timestamp}.png"

        try:
            extra_args = {
                "ContentType": "image/png",
                "CacheControl": "max-age=31536000, public",
            }
            # Upload permanent key (always accessible at standard URL)
            client.upload_file(local_filepath, self.bucket_name, main_key, ExtraArgs=extra_args)
            print(f"  [S3] Successfully uploaded new screenshot to {self.bucket_name}/{main_key}")

            # Also upload versioned key for cache busting
            try:
                client.upload_file(local_filepath, self.bucket_name, versioned_key, ExtraArgs=extra_args)
            except Exception:
                pass

            if self.public_url_base:
                return f"{self.public_url_base}/{main_key}"
            return f"{self.endpoint_url}/{self.bucket_name}/{main_key}"
        except Exception as exc:
            print(f"  [S3 Error] Failed to upload {local_filepath} to S3: {exc}")
            import traceback
            traceback.print_exc()
            return standard_s3_url
