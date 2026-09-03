from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so Base.metadata knows about them for create_all()
# and so Alembic (if added later) can autogenerate migrations correctly.
from app.models.user import User  # noqa: E402,F401
from app.models.folder import Folder  # noqa: E402,F401
from app.models.file import File  # noqa: E402,F401
from app.models.file_version import FileVersion  # noqa: E402,F401
from app.models.share import Share  # noqa: E402,F401
from app.models.link_share import LinkShare  # noqa: E402,F401
from app.models.star import Star  # noqa: E402,F401
from app.models.activity import Activity  # noqa: E402,F401
