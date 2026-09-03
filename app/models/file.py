from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class File(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "files"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    folder_id: Mapped[str | None] = mapped_column(
        ForeignKey("folders.id"), nullable=True, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    is_trashed: Mapped[bool] = mapped_column(Boolean, default=False)
    trashed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version: Mapped[int] = mapped_column(default=1)

    owner = relationship("User", back_populates="files")
    folder = relationship("Folder")
    versions = relationship(
        "FileVersion", back_populates="file", cascade="all, delete-orphan",
        order_by="FileVersion.version_number",
    )
