from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import ensure_access, get_current_user
from app.core.security import create_share_token, hash_password, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models.file import File
from app.models.folder import Folder
from app.models.link_share import LinkShare
from app.models.share import Share
from app.models.user import User
from app.schemas.file import FileOut
from app.schemas.folder import FolderOut
from app.schemas.share import PublicLinkCreate, PublicLinkOut, ShareCreate, ShareOut
from app.utils.activity import log_activity
from app.utils.serialize import file_to_out

router = APIRouter(tags=["sharing"])


def _share_out(share: Share, email: str | None) -> ShareOut:
    return ShareOut(
        id=share.id,
        resource_type=share.resource_type.value if hasattr(share.resource_type, "value") else share.resource_type,
        resource_id=share.resource_id,
        owner_id=share.owner_id,
        shared_with_id=share.shared_with_id,
        shared_with_email=email,
        role=share.role.value if hasattr(share.role, "value") else share.role,
        created_at=share.created_at,
    )


@router.post("/shares", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
def create_share(payload: ShareCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, payload.resource_type, payload.resource_id, min_role="owner")

    target_user = db.query(User).filter(User.email == payload.email).first()
    if target_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    if target_user.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot share a resource with yourself")

    existing = (
        db.query(Share)
        .filter(
            Share.resource_type == payload.resource_type,
            Share.resource_id == payload.resource_id,
            Share.shared_with_id == target_user.id,
        )
        .first()
    )
    if existing:
        existing.role = payload.role
        share = existing
    else:
        share = Share(
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            owner_id=user.id,
            shared_with_id=target_user.id,
            role=payload.role,
        )
        db.add(share)

    log_activity(db, user.id, "share", payload.resource_type, payload.resource_id, f"with {payload.email}")
    db.commit()
    db.refresh(share)
    return _share_out(share, target_user.email)


@router.get("/shares", response_model=list[ShareOut])
def list_shares(
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_access(db, user, resource_type, resource_id, min_role="owner")
    shares = (
        db.query(Share)
        .filter(Share.resource_type == resource_type, Share.resource_id == resource_id)
        .all()
    )
    out = []
    for s in shares:
        target = db.get(User, s.shared_with_id)
        out.append(_share_out(s, target.email if target else None))
    return out


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_share(share_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    share = db.get(Share, share_id)
    if share is None or share.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    db.delete(share)
    db.commit()
    return None


@router.get("/shared-with-me", response_model=list[ShareOut])
def shared_with_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shares = db.query(Share).filter(Share.shared_with_id == user.id).all()
    out = []
    for s in shares:
        owner = db.get(User, s.owner_id)
        out.append(_share_out(s, owner.email if owner else None))
    return out


# ---------------------------------------------------------------------------
# Public shareable links
# ---------------------------------------------------------------------------


def _link_out(link: LinkShare) -> PublicLinkOut:
    return PublicLinkOut(
        id=link.id,
        token=link.token,
        resource_type=link.resource_type,
        resource_id=link.resource_id,
        role=link.role,
        expires_at=link.expires_at,
        has_password=bool(link.password_hash),
        url=f"{settings.FRONTEND_URL}/share/{link.token}",
    )


@router.post("/public-link", response_model=PublicLinkOut, status_code=status.HTTP_201_CREATED)
def create_public_link(payload: PublicLinkCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_access(db, user, payload.resource_type, payload.resource_id, min_role="owner")

    expires_at = None
    if payload.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)

    link = LinkShare(
        token=create_share_token(),
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        owner_id=user.id,
        role=payload.role,
        expires_at=expires_at,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(link)
    log_activity(db, user.id, "create_link", payload.resource_type, payload.resource_id, "")
    db.commit()
    db.refresh(link)
    return _link_out(link)


@router.get("/public-link", response_model=list[PublicLinkOut])
def list_public_links(
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_access(db, user, resource_type, resource_id, min_role="owner")
    links = (
        db.query(LinkShare)
        .filter(LinkShare.resource_type == resource_type, LinkShare.resource_id == resource_id)
        .all()
    )
    return [_link_out(l) for l in links]


@router.delete("/public-link/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_public_link(link_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    link = db.get(LinkShare, link_id)
    if link is None or link.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    db.delete(link)
    db.commit()
    return None


def _resolve_link(db: Session, token: str, password: str | None) -> LinkShare:
    link = db.query(LinkShare).filter(LinkShare.token == token).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    if link.expires_at and link.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_410_GONE, "This link has expired")
    if link.password_hash:
        if not password or not verify_password(password, link.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password required or incorrect")
    return link


@router.get("/public/{token}")
def resolve_public_link(token: str, password: str | None = None, db: Session = Depends(get_db)):
    link = _resolve_link(db, token, password)

    if link.resource_type == "file":
        file = db.get(File, link.resource_id)
        if file is None or file.is_trashed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

        # Always route through our own public download endpoint (below) rather
        # than handing out the authenticated /files/blob path directly - that
        # path requires a login, which a public/anonymous visitor won't have.
        password_qs = f"?{urlencode({'password': password})}" if password else ""
        return {
            "resource_type": "file",
            "file": FileOut.model_validate(file).model_dump(exclude={"is_starred"}),
            "download_url": f"/public/{token}/download{password_qs}",
            "role": link.role,
        }
    else:
        folder = db.get(Folder, link.resource_id)
        if folder is None or folder.is_trashed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
        folders = db.query(Folder).filter(Folder.parent_id == folder.id, Folder.is_trashed.is_(False)).all()
        files = db.query(File).filter(File.folder_id == folder.id, File.is_trashed.is_(False)).all()
        return {
            "resource_type": "folder",
            "folder": FolderOut.model_validate(folder).model_dump(),
            "folders": [FolderOut.model_validate(f).model_dump() for f in folders],
            "files": [FileOut.model_validate(f).model_dump(exclude={"is_starred"}) for f in files],
            "role": link.role,
        }


@router.get("/public/{token}/download")
def download_public_file(token: str, password: str | None = None, db: Session = Depends(get_db)):
    """Unauthenticated download for a file public-link - no login required."""
    link = _resolve_link(db, token, password)
    if link.resource_type != "file":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is not a file link")

    file = db.get(File, link.resource_id)
    if file is None or file.is_trashed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    from app.services.storage import LocalStorage, get_storage

    storage = get_storage()
    if isinstance(storage, LocalStorage):
        data = storage.read_bytes(file.storage_key)

        def _iter():
            yield data

        return StreamingResponse(
            _iter(),
            media_type=file.mime_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file.name}"'},
        )

    url, _ = storage.build_download_url(file.storage_key, file.name)
    return RedirectResponse(url)
