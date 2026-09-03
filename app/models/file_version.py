from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class FileVersion(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "file_versions"

    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(default=1)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    uploaded_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    file = relationship("File", back_populates="versions")
