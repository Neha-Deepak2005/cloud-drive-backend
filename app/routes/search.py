from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.file import File
from app.models.folder import Folder
from app.models.share import Share
from app.models.user import User
from app.schemas.folder import FolderOut
from app.utils.serialize import files_to_out

router = APIRouter(tags=["search"])


@router.get("/search")
def search(
    q: str = Query("", min_length=0, max_length=255),
    type: str = Query("all", pattern="^(all|file|folder)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shared_file_ids = [
        s.resource_id for s in db.query(Share).filter(Share.shared_with_id == user.id, Share.resource_type == "file")
    ]
    shared_folder_ids = [
        s.resource_id
        for s in db.query(Share).filter(Share.shared_with_id == user.id, Share.resource_type == "folder")
    ]

    files_out = []
    if type in ("all", "file"):
        query = db.query(File).filter(
            File.is_trashed.is_(False),
            or_(File.owner_id == user.id, File.id.in_(shared_file_ids) if shared_file_ids else False),
        )
        if q:
            query = query.filter(File.name.ilike(f"%{q}%"))
        files_out = files_to_out(db, user.id, query.order_by(File.name).limit(200).all())

    folders_out = []
    if type in ("all", "folder"):
        query = db.query(Folder).filter(
            Folder.is_trashed.is_(False),
            or_(Folder.owner_id == user.id, Folder.id.in_(shared_folder_ids) if shared_folder_ids else False),
        )
        if q:
            query = query.filter(Folder.name.ilike(f"%{q}%"))
        folders_out = [FolderOut.model_validate(f) for f in query.order_by(Folder.name).limit(200).all()]

    return {"files": files_out, "folders": folders_out}
