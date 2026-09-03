from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import ensure_access, get_current_user
from app.db.session import get_db
from app.models.file import File
from app.models.file_version import FileVersion
from app.models.folder import Folder
from app.models.star import Star
from app.models.user import User
from app.schemas.file import (
    CompleteUploadRequest,
    DownloadUrlOut,
    FileOut,
    FileUpdate,
    InitUploadRequest,
    InitUploadResponse,
)
from app.services.storage import LocalStorage, get_storage, make_storage_key
from app.utils.activity import log_activity
from app.utils.serialize import file_to_out

router = APIRouter(prefix="/files", tags=["files"])

# Small blocklist of dangerous executable types, per the security checklist.
_BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".msi", ".com", ".scr"}


@router.post("/init-upload", response_model=InitUploadResponse)
def init_upload(payload: InitUploadRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if payload.size_bytes > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )
    lower_name = payload.name.lower()
    if any(lower_name.endswith(ext) for ext in _BLOCKED_EXTENSIONS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File type not allowed")

    if payload.folder_id:
        ensure_access(db, user, "folder", payload.folder_id, min_role="editor")

    storage_key = make_storage_key(user.id, payload.name)
    target = get_storage().build_upload_target(storage_key, payload.mime_type)
    return InitUploadResponse(
        upload_id=storage_key,
        method=target["method"],
        upload_url=target["upload_url"],
        fields=target.get("fields", {}),
        storage_key=storage_key,
    )


@router.post("/upload-blob", status_code=status.HTTP_201_CREATED)
async def upload_blob(
    storage_key: str,
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    """Local-storage-driver only: receives the raw bytes directly."""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Direct upload not used with this storage driver")
    if not storage_key.startswith(f"{user.id}/"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid storage key")

    data = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
    storage.save_bytes(storage_key, data)
    return {"storage_key": storage_key, "size_bytes": len(data)}


@router.post("/complete-upload", response_model=FileOut, status_code=status.HTTP_201_CREATED)
def complete_upload(
    payload: CompleteUploadRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not payload.storage_key.startswith(f"{user.id}/"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid storage key")

    if payload.file_id:
        # Re-upload: create a new version of an existing file.
        ensure_access(db, user, "file", payload.file_id, min_role="editor")
        file = db.get(File, payload.file_id)
        new_version_number = file.current_version + 1
        db.add(
            FileVersion(
                file_id=file.id,
                version_number=new_version_number,
                storage_key=payload.storage_key,
                size_bytes=payload.size_bytes,
                uploaded_by_id=user.id,
            )
        )
        file.storage_key = payload.storage_key
        file.size_bytes = payload.size_bytes
        file.mime_type = payload.mime_type
        file.current_version = new_version_number
        log_activity(db, user.id, "upload_version", "file", file.id, f"v{new_version_number}")
    else:
        if payload.folder_id:
            ensure_access(db, user, "folder", payload.folder_id, min_role="editor")
        file = File(
            name=payload.name,
            owner_id=user.id,
            folder_id=payload.folder_id,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            current_version=1,
        )
        db.add(file)
        db.flush()
        db.add(
            FileVersion(
                file_id=file.id,
                version_number=1,
                storage_key=payload.storage_key,
                size_bytes=payload.size_bytes,
                uploaded_by_id=user.id,
            )
        )
        log_activity(db, user.id, "upload", "file", file.id, payload.name)

    db.commit()
    db.refresh(file)
    return file_to_out(db, user.id, file)


@router.get("/blob/{storage_key:path}")
def get_blob(storage_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Local-storage-driver only: authenticated raw byte stream for a file the user can access."""
    file = db.query(File).filter(File.storage_key == storage_key).first()
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    ensure_access(db, user, "file", file.id, min_role="viewer")

    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not served locally")
    data = storage.read_bytes(storage_key)

    def _iter():
        yield data

    return StreamingResponse(
        _iter(),
        media_type=file.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file.name}"'},
    )


@router.get("/{file_id}", response_model=FileOut)
def get_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "file", file_id, min_role="viewer")
    return file_to_out(db, user.id, db.get(File, file_id))


@router.get("/{file_id}/download", response_model=DownloadUrlOut)
def get_download_url(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "file", file_id, min_role="viewer")
    file = db.get(File, file_id)
    url, expires_in = get_storage().build_download_url(file.storage_key, file.name)
    log_activity(db, user.id, "download", "file", file.id, file.name)
    db.commit()
    return DownloadUrlOut(url=url, expires_in=expires_in)


@router.patch("/{file_id}", response_model=FileOut)
def update_file(file_id: str, payload: FileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "file", file_id, min_role="editor")
    file = db.get(File, file_id)

    if payload.folder_id is not None and payload.folder_id != file.folder_id:
        if payload.folder_id:
            ensure_access(db, user, "folder", payload.folder_id, min_role="editor")
        file.folder_id = payload.folder_id or None
    if payload.name is not None:
        file.name = payload.name

    log_activity(db, user.id, "update", "file", file.id, file.name)
    db.commit()
    db.refresh(file)
    return file_to_out(db, user.id, file)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def trash_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "file", file_id, min_role="editor")
    file = db.get(File, file_id)
    file.is_trashed = True
    file.trashed_at = datetime.now(timezone.utc)
    log_activity(db, user.id, "trash", "file", file.id, file.name)
    db.commit()
    return None


@router.post("/{file_id}/restore", response_model=FileOut)
def restore_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    file = db.get(File, file_id)
    if file is None or file.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    file.is_trashed = False
    file.trashed_at = None
    log_activity(db, user.id, "restore", "file", file.id, file.name)
    db.commit()
    db.refresh(file)
    return file_to_out(db, user.id, file)


@router.post("/{file_id}/star", response_model=FileOut)
def star_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "file", file_id, min_role="viewer")
    file = db.get(File, file_id)
    exists = db.query(Star).filter(Star.user_id == user.id, Star.file_id == file_id).first()
    if not exists:
        db.add(Star(user_id=user.id, file_id=file_id))
    db.commit()
    db.refresh(file)
    return file_to_out(db, user.id, file)


@router.delete("/{file_id}/star", response_model=FileOut)
def unstar_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, "file", file_id, min_role="viewer")
    file = db.get(File, file_id)
    db.query(Star).filter(Star.user_id == user.id, Star.file_id == file_id).delete()
    db.commit()
    db.refresh(file)
    return file_to_out(db, user.id, file)
