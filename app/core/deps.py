"""
FastAPI dependencies: current DB session, current authenticated user,
and resource-level permission checks (owner / editor / viewer).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.file import File
from app.models.folder import Folder
from app.models.share import Share, ShareRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def _effective_role_for(db: Session, user: User, resource_type: str, resource_id: str) -> str | None:
    """
    Returns "owner" | "editor" | "viewer" | None (no access) for the given user
    on the given resource, taking direct ownership and Share rows into account.
    Folder shares are NOT automatically inherited by children in this MVP
    (kept simple - each resource is shared explicitly), matching the "All
    permission checks are enforced server-side" requirement from the spec.
    """
    if resource_type == "file":
        resource = db.get(File, resource_id)
    else:
        resource = db.get(Folder, resource_id)

    if resource is None:
        return None
    if resource.owner_id == user.id:
        return "owner"

    share = (
        db.query(Share)
        .filter(
            Share.resource_type == resource_type,
            Share.resource_id == resource_id,
            Share.shared_with_id == user.id,
        )
        .first()
    )
    if share is None:
        return None
    return share.role.value if isinstance(share.role, ShareRole) else share.role


_RANK = {"viewer": 0, "editor": 1, "owner": 2}


def get_effective_role(db: Session, user: User, resource_type: str, resource_id: str) -> str | None:
    return _effective_role_for(db, user, resource_type, resource_id)


def ensure_access(db: Session, user: User, resource_type: str, resource_id: str, min_role: str = "viewer") -> str:
    """
    Call from inside a route body (once the path-param resource_id is known)
    to enforce that `user` has at least `min_role` on the resource.
    Returns the effective role, or raises 403/404.
    """
    role = _effective_role_for(db, user, resource_type, resource_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{resource_type.capitalize()} not found")
    if _RANK[role] < _RANK[min_role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    return role
