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
            or ""
        ).rstrip("/")
        self.region_name = (
            region_name
            or os.getenv("S3_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_S3_REGION_NAME")
            or ""
        )
        self.bucket_name = (
            bucket_name
            or os.getenv("S3_BUCKET_NAME")
            or os.getenv("AWS_STORAGE_BUCKET_NAME")
            or os.getenv("BUCKET_NAME")
            or ""
        )
        self.access_key_id = (
            access_key_id
            or os.getenv("S3_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("ACCESS_KEY_ID")
            or os.getenv("TIGRIS_ACCESS_KEY_ID")
            or ""
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
            or os.getenv("SECRET_KEY")
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
            print("  [S3 Error] boto3 library is not installed! Please run: pip install boto3")
            return None
        if not self.is_configured():
            print(f"  [S3 Warning] S3 credentials incomplete (key_id={bool(self.access_key_id)}, secret_key={bool(self.secret_access_key)}, bucket={bool(self.bucket_name)})")
            return None

        if self._client is None:
            try:
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    region_name=self.region_name,
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    config=Config(s3={"addressing_style": "path"}),
                )
            except Exception as e:
                print(f"  [S3 Error] Failed to initialize boto3 client: {e}")
                return None
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

    def cleanup_old_versioned_screenshots(self, group_prefix: Optional[str] = None):
        """
        Deletes any old timestamped/versioned timetable screenshots (timetables/*_*.png)
        to prevent filling up S3 bucket storage.
        """
        client = self.get_client()
        if not client:
            return

        prefix = f"timetables/{group_prefix}_" if group_prefix else "timetables/"
        try:
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            to_delete = []

            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj.get("Key", "")
                    # Match any versioned timestamp screenshot e.g. timetables/CIE26-1_172561234.png
                    if "_" in key and key.endswith(".png"):
                        to_delete.append({"Key": key})

            if to_delete:
                # Delete in batches of 1000 (S3 API limit)
                for i in range(0, len(to_delete), 1000):
                    batch = to_delete[i:i + 1000]
                    client.delete_objects(Bucket=self.bucket_name, Delete={"Objects": batch})
                print(f"  [S3 Storage Cleanup] Successfully purged {len(to_delete)} old timetable screenshots.")
        except Exception as exc:
            print(f"  [S3 Cleanup Warning] Error purging old screenshots: {exc}")

    def upload_timetable_screenshot(
        self,
        group_name: str,
        local_filepath: str,
        old_image_url: Optional[str] = None,
        use_timestamp: bool = True,
    ) -> Optional[str]:
        """
        1. Deletes old timetable screenshots for this group from S3 (both old_image_url and any versioned keys).
        2. Uploads the single canonical screenshot to S3 (timetables/{group}.png).
        3. Returns the S3 URL with a ?v=timestamp query param for instant cache busting without storing extra files.
        """
        sanitized_grp = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name).strip("._") or "group"
        standard_s3_url = self.get_public_url(group_name)

        if not os.path.exists(local_filepath):
            print(f"  [S3 Error] File does not exist: {local_filepath}")
            return standard_s3_url

        client = self.get_client()
        if not client:
            return standard_s3_url

        # 1. Proactively purge old versioned files for this group from S3
        self.cleanup_old_versioned_screenshots(group_prefix=sanitized_grp)

        # 2. Remove explicit old photo key if different from canonical
        main_key = f"timetables/{sanitized_grp}.png"
        if old_image_url:
            old_key = self.extract_s3_key_from_url(old_image_url)
            if old_key and old_key != main_key:
                self.delete_object(old_key)

        # 3. Upload single canonical file to S3 (overwriting existing in-place)
        timestamp = int(time.time())
        try:
            extra_args = {
                "ContentType": "image/png",
                "CacheControl": "public, max-age=3600, must-revalidate",
            }
            client.upload_file(local_filepath, self.bucket_name, main_key, ExtraArgs=extra_args)
            print(f"  [S3] Successfully updated screenshot for {group_name} in {self.bucket_name}/{main_key}")

            base_url = (
                f"{self.public_url_base}/{main_key}"
                if self.public_url_base
                else f"{self.endpoint_url}/{self.bucket_name}/{main_key}"
            )
            # Add cache-busting query string without creating extra files in S3!
            return f"{base_url}?v={timestamp}" if use_timestamp else base_url
        except Exception as exc:
            print(f"  [S3 Error] Failed to upload {local_filepath} to S3: {exc}")
            import traceback
            traceback.print_exc()
            return standard_s3_url
