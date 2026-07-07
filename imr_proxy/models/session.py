from datetime import datetime, timezone
from pydantic import BaseModel, Field
class SessionRecord(BaseModel):
    id: str
    name: str
    version: str
    created_at: datetime=Field(default_factory=lambda: datetime.now(timezone.utc))
    config_snapshot: dict=Field(default_factory=dict)
