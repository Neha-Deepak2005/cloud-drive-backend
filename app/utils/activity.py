from sqlalchemy.orm import Session

from app.models.activity import Activity


def log_activity(db: Session, user_id: str, action: str, resource_type: str, resource_id: str, detail: str = ""):
    db.add(
        Activity(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
        )
    )
