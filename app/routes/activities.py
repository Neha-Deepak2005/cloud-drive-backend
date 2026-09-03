from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.activity import Activity
from app.models.user import User
from app.schemas.activity import ActivityOut

router = APIRouter(tags=["activities"])


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    limit: int = Query(50, ge=1, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return (
        db.query(Activity)
        .filter(Activity.user_id == user.id)
        .order_by(Activity.created_at.desc())
        .limit(limit)
        .all()
    )
