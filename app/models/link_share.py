from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin
from app.models.share import ResourceType


class LinkShare(Base, UUIDPKMixin, TimestampMixin):
    """A public, token-based share link, optionally expiring / password protected."""

    __tablename__ = "link_shares"

    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    resource_type: Mapped[ResourceType] = mapped_column(String(20), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # viewer | editor
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
