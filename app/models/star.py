from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Star(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "stars"
    __table_args__ = (UniqueConstraint("user_id", "file_id", name="uq_star_user_file"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), nullable=False, index=True)
