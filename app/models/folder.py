from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Folder(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "folders"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("folders.id"), nullable=True, index=True
    )
    is_trashed: Mapped[bool] = mapped_column(Boolean, default=False)
    trashed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="folders")
    parent = relationship("Folder", remote_side="Folder.id", backref="children")
