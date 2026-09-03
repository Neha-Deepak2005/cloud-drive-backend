from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.file import File
from app.models.star import Star
from app.models.user import User
from app.schemas.file import FileOut
from app.utils.serialize import files_to_out

router = APIRouter(tags=["starred"])


@router.get("/starred", response_model=list[FileOut])
def list_starred(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    file_ids = [s.file_id for s in db.query(Star).filter(Star.user_id == user.id).all()]
    if not file_ids:
        return []
    files = db.query(File).filter(File.id.in_(file_ids), File.is_trashed.is_(False)).order_by(File.name).all()
    return files_to_out(db, user.id, files)
