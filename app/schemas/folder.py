from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: str | None = None


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_id: str
    parent_id: str | None
    is_trashed: bool
    created_at: datetime
    updated_at: datetime


class BreadcrumbItem(BaseModel):
    id: str
    name: str


class FolderContents(BaseModel):
    folder: FolderOut | None  # None = root
    breadcrumbs: list[BreadcrumbItem]
    folders: list[FolderOut]
    files: list["FileOut"]  # forward ref, resolved in __init__.py


from app.schemas.file import FileOut  # noqa: E402

FolderContents.model_rebuild()
