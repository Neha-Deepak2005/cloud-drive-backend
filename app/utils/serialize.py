"""
Per-user-correct serialization helpers.

`File.is_starred` is a convenience column but stars are actually per-user
(see the `stars` table), so a file shared between two users must not show
as starred for both just because one of them starred it. These helpers
compute the correct, current-user-scoped value instead of trusting the
raw column.
"""
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.star import Star
from app.schemas.file import FileOut


def file_to_out(db: Session, user_id: str, file: File) -> FileOut:
    starred = db.query(Star).filter(Star.user_id == user_id, Star.file_id == file.id).first() is not None
    data = FileOut.model_validate(file).model_dump()
    data["is_starred"] = starred
    return FileOut(**data)


def files_to_out(db: Session, user_id: str, files: list[File]) -> list[FileOut]:
    starred_ids = {
        s.file_id
        for s in db.query(Star.file_id).filter(Star.user_id == user_id, Star.file_id.in_([f.id for f in files])).all()
    } if files else set()
    out = []
    for f in files:
        data = FileOut.model_validate(f).model_dump()
        data["is_starred"] = f.id in starred_ids
        out.append(FileOut(**data))
    return out
