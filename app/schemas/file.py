from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InitUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    folder_id: str | None = None
    mime_type: str = "application/octet-stream"
    size_bytes: int = Field(ge=0)


class InitUploadResponse(BaseModel):
    upload_id: str
    method: str  # "direct" (local, PUT to our API) | "signed" (upload straight to storage)
    upload_url: str
    fields: dict = {}
    storage_key: str


class CompleteUploadRequest(BaseModel):
    upload_id: str
    storage_key: str
    name: str
    folder_id: str | None = None
    mime_type: str = "application/octet-stream"
    size_bytes: int = Field(ge=0)
    # set when re-uploading an existing file id to create a new version
    file_id: str | None = None


class FileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    folder_id: str | None = None


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_id: str
    folder_id: str | None
    mime_type: str
    size_bytes: int
    is_starred: bool
    is_trashed: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class DownloadUrlOut(BaseModel):
    url: str
    expires_in: int
