import enum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ShareRole(str, enum.Enum):
    viewer = "viewer"
    editor = "editor"


class ResourceType(str, enum.Enum):
    file = "file"
    folder = "folder"


class Share(Base, UUIDPKMixin, TimestampMixin):
    """A file/folder shared with a specific user (by email/user id)."""

    __tablename__ = "shares"

    resource_type: Mapped[ResourceType] = mapped_column(Enum(ResourceType), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    shared_with_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[ShareRole] = mapped_column(Enum(ShareRole), default=ShareRole.viewer)

    owner = relationship("User", foreign_keys=[owner_id])
    shared_with = relationship("User", foreign_keys=[shared_with_id])
