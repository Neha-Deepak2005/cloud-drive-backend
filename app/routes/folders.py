from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import ensure_access, get_current_user
from app.db.session import get_db
from app.models.file import File
from app.models.folder import Folder
from app.models.user import User
from app.schemas.file import FileOut
from app.schemas.folder import BreadcrumbItem, FolderContents, FolderCreate, FolderOut, FolderUpdate
from app.utils.activity import log_activity
from app.utils.serialize import files_to_out

router = APIRouter(prefix="/folders", tags=["folders"])


def _breadcrumbs(db: Session, folder: Folder | None) -> list[BreadcrumbItem]:
    trail: list[BreadcrumbItem] = []
    current = folder
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        trail.append(BreadcrumbItem(id=current.id, name=current.name))
        current = db.get(Folder, current.parent_id) if current.parent_id else None
    trail.reverse()
    return trail


def _is_self_or_descendant(db: Session, ancestor_id: str, folder_id: str) -> bool:
    """True if folder_id is ancestor_id itself or nested somewhere under it."""
    current = db.get(Folder, folder_id)
    while current is not None:
        if current.id == ancestor_id:
            return True
        current = db.get(Folder, current.parent_id) if current.parent_id else None
    return False


def _trash_recursive(db: Session, folder: Folder, now: datetime):
    folder.is_trashed = True
    folder.trashed_at = now
    for child in db.query(Folder).filter(Folder.parent_id == folder.id, Folder.is_trashed.is_(False)):
        _trash_recursive(db, child, now)
    for f in db.query(File).filter(File.folder_id == folder.id, File.is_trashed.is_(False)):
        f.is_trashed = True
        f.trashed_at = now


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.parent_id:
        ensure_access(db, user, "folder", payload.parent_id, min_role="editor")

    folder = Folder(name=payload.name, owner_id=user.id, parent_id=payload.parent_id)
    db.add(folder)
    db.flush()
    log_activity(db, user.id, "create", "folder", folder.id, payload.name)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("/root", response_model=FolderContents)
def get_root(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folders = (
        db.query(Folder)
        .filter(Folder.owner_id == user.id, Folder.parent_id.is_(None), Folder.is_trashed.is_(False))
        .order_by(Folder.name)
        .all()
    )
    files = (
        db.query(File)
        .filter(File.owner_id == user.id, File.folder_id.is_(None), File.is_trashed.is_(False))
        .order_by(File.name)
        .all()
    )
    return FolderContents(
        folder=None,
        breadcrumbs=[],
        folders=[FolderOut.model_validate(f) for f in folders],
        files=files_to_out(db, user.id, files),
    )


@router.get("/{folder_id}", response_model=FolderContents)
def get_folder(folder_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "folder", folder_id, min_role="viewer")
    folder = db.get(Folder, folder_id)

    folders = (
        db.query(Folder)
        .filter(Folder.parent_id == folder_id, Folder.is_trashed.is_(False))
        .order_by(Folder.name)
        .all()
    )
    files = (
        db.query(File)
        .filter(File.folder_id == folder_id, File.is_trashed.is_(False))
        .order_by(File.name)
        .all()
    )
    return FolderContents(
        folder=FolderOut.model_validate(folder),
        breadcrumbs=_breadcrumbs(db, folder),
        folders=[FolderOut.model_validate(f) for f in folders],
        files=files_to_out(db, user.id, files),
    )


@router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: str, payload: FolderUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    ensure_access(db, user, "folder", folder_id, min_role="editor")
    folder = db.get(Folder, folder_id)

    if payload.parent_id is not None and payload.parent_id != folder.parent_id:
        if payload.parent_id == folder.id or _is_self_or_descendant(db, folder.id, payload.parent_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot move a folder into itself or its descendant")
        if payload.parent_id:
            ensure_access(db, user, "folder", payload.parent_id, min_role="editor")
        folder.parent_id = payload.parent_id or None

    if payload.name is not None:
        folder.name = payload.name

    log_activity(db, user.id, "update", "folder", folder.id, folder.name)
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def trash_folder(folder_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "folder", folder_id, min_role="editor")
    folder = db.get(Folder, folder_id)
    _trash_recursive(db, folder, datetime.now(timezone.utc))
    log_activity(db, user.id, "trash", "folder", folder.id, folder.name)
    db.commit()
    return None


@router.post("/{folder_id}/restore", response_model=FolderOut)
def restore_folder(folder_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = db.get(Folder, folder_id)
    if folder is None or folder.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
    folder.is_trashed = False
    folder.trashed_at = None
    log_activity(db, user.id, "restore", "folder", folder.id, folder.name)
    db.commit()
    db.refresh(folder)
    return folder
