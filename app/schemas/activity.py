from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    detail: str
    created_at: datetime
