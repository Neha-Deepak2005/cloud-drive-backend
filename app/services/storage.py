"""
Storage abstraction so the rest of the app never talks to disk / S3 directly.

Two drivers, selected by STORAGE_DRIVER env var:
  - "local"    : files saved under LOCAL_STORAGE_DIR on the backend's own disk.
                 Good for zero-setup local dev; NOT suitable for most hosts with
                 ephemeral filesystems (e.g. Render free tier) in production.
  - "supabase" : Supabase Storage, accessed via its S3-compatible API (boto3).
                 Also works for plain AWS S3 by pointing the endpoint/keys there.
"""
import abc
import mimetypes
import os
import uuid
from datetime import timedelta

from app.core.config import settings


def make_storage_key(owner_id: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1]
    return f"{owner_id}/{uuid.uuid4().hex}{ext}"


class BaseStorage(abc.ABC):
    @abc.abstractmethod
    def build_upload_target(self, storage_key: str, mime_type: str) -> dict:
        """Return info the frontend needs to actually upload the bytes."""

    @abc.abstractmethod
    def build_download_url(self, storage_key: str, download_name: str) -> tuple[str, int]:
        """Return (url, expires_in_seconds) the frontend can GET to download the file."""

    @abc.abstractmethod
    def save_bytes(self, storage_key: str, data: bytes):
        """Used by the local-driver direct-upload endpoint."""

    @abc.abstractmethod
    def delete(self, storage_key: str):
        ...


class LocalStorage(BaseStorage):
    def __init__(self):
        self.root = settings.LOCAL_STORAGE_DIR
        os.makedirs(self.root, exist_ok=True)

    def _path(self, storage_key: str) -> str:
        path = os.path.normpath(os.path.join(self.root, storage_key))
        if not path.startswith(os.path.normpath(self.root)):
            raise ValueError("Invalid storage key")
        return path

    def build_upload_target(self, storage_key: str, mime_type: str) -> dict:
        # Client uploads via our own multipart endpoint, not a raw disk path.
        return {
            "method": "direct",
            "upload_url": "/files/upload-blob",
            "fields": {"storage_key": storage_key},
        }

    def build_download_url(self, storage_key: str, download_name: str) -> tuple[str, int]:
        # Served by our own authenticated download endpoint; storage_key is
        # passed through as a query param, resolved server-side (see files.py).
        return f"/files/blob/{storage_key}", 3600

    def save_bytes(self, storage_key: str, data: bytes):
        path = self._path(storage_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def read_bytes(self, storage_key: str) -> bytes:
        with open(self._path(storage_key), "rb") as f:
            return f.read()

    def delete(self, storage_key: str):
        path = self._path(storage_key)
        if os.path.exists(path):
            os.remove(path)


class SupabaseS3Storage(BaseStorage):
    """Uses Supabase Storage's S3-compatible endpoint via boto3 presigned URLs."""

    def __init__(self):
        import boto3

        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.SUPABASE_S3_ENDPOINT,
            region_name=settings.SUPABASE_S3_REGION,
            aws_access_key_id=settings.SUPABASE_S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.SUPABASE_S3_SECRET_ACCESS_KEY,
        )

    def build_upload_target(self, storage_key: str, mime_type: str) -> dict:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": storage_key, "ContentType": mime_type},
            ExpiresIn=900,
        )
        return {"method": "signed", "upload_url": url, "fields": {}}

    def build_download_url(self, storage_key: str, download_name: str) -> tuple[str, int]:
        expires_in = 3600
        content_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
        url = self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": storage_key,
                "ResponseContentDisposition": f'attachment; filename="{download_name}"',
                "ResponseContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url, expires_in

    def save_bytes(self, storage_key: str, data: bytes):
        self.client.put_object(Bucket=self.bucket, Key=storage_key, Body=data)

    def delete(self, storage_key: str):
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)


_instance: BaseStorage | None = None


def get_storage() -> BaseStorage:
    global _instance
    if _instance is None:
        if settings.STORAGE_DRIVER == "supabase":
            _instance = SupabaseS3Storage()
        else:
            _instance = LocalStorage()
    return _instance
