from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.file import File
from app.models.file_version import FileVersion
from app.models.folder import Folder
from app.models.star import Star
from app.models.user import User
from app.schemas.folder import FolderOut
from app.services.storage import get_storage
from app.utils.activity import log_activity
from app.utils.serialize import files_to_out

router = APIRouter(prefix="/trash", tags=["trash"])


@router.get("")
def list_trash(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    files = db.query(File).filter(File.owner_id == user.id, File.is_trashed.is_(True)).order_by(File.trashed_at.desc()).all()
    folders = (
        db.query(Folder)
        .filter(Folder.owner_id == user.id, Folder.is_trashed.is_(True))
        .order_by(Folder.trashed_at.desc())
        .all()
    )
    return {"files": files_to_out(db, user.id, files), "folders": [FolderOut.model_validate(f) for f in folders]}


def _permanently_delete_file(db: Session, file: File):
    storage = get_storage()
    for version in db.query(FileVersion).filter(FileVersion.file_id == file.id):
        try:
            storage.delete(version.storage_key)
        except Exception:
            pass
    db.query(Star).filter(Star.file_id == file.id).delete()
    db.delete(file)


def _permanently_delete_folder(db: Session, folder: Folder):
    for child in db.query(Folder).filter(Folder.parent_id == folder.id):
        _permanently_delete_folder(db, child)
    for f in db.query(File).filter(File.folder_id == folder.id):
        _permanently_delete_file(db, f)
    db.delete(folder)


@router.delete("/file/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    file = db.get(File, file_id)
    if file is None or file.owner_id != user.id or not file.is_trashed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found in trash")
    log_activity(db, user.id, "delete_permanent", "file", file.id, file.name)
    _permanently_delete_file(db, file)
    db.commit()
    return None


@router.delete("/folder/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_folder(folder_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = db.get(Folder, folder_id)
    if folder is None or folder.owner_id != user.id or not folder.is_trashed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found in trash")
    log_activity(db, user.id, "delete_permanent", "folder", folder.id, folder.name)
    _permanently_delete_folder(db, folder)
    db.commit()
    return None


@router.post("/empty", status_code=status.HTTP_204_NO_CONTENT)
def empty_trash(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for f in db.query(File).filter(File.owner_id == user.id, File.is_trashed.is_(True)).all():
        _permanently_delete_file(db, f)
    for folder in (
        db.query(Folder)
        .filter(Folder.owner_id == user.id, Folder.is_trashed.is_(True), Folder.parent_id.is_(None))
        .all()
    ):
        _permanently_delete_folder(db, folder)
    log_activity(db, user.id, "empty_trash", "user", user.id, "")
    db.commit()
    return None
