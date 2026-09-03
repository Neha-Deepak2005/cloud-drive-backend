from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ShareCreate(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: str
    email: EmailStr
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resource_type: str
    resource_id: str
    owner_id: str
    shared_with_id: str
    shared_with_email: str | None = None
    role: str
    created_at: datetime


class PublicLinkCreate(BaseModel):
    resource_type: str = Field(pattern="^(file|folder)$")
    resource_id: str
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")
    expires_in_hours: int | None = None
    password: str | None = None


class PublicLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    token: str
    resource_type: str
    resource_id: str
    role: str
    expires_at: datetime | None
    has_password: bool
    url: str
