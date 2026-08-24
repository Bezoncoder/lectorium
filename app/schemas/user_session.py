from datetime import datetime

from app.schemas.base import BasePydantic


class UserSessionPydantic(BasePydantic):
    id: int
    user_id: int
    expires_at: datetime
    last_used_at: datetime
    ip_address: str | None
    user_agent: str | None
    created_at: datetime