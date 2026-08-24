from app.db.dao.base import BaseDAO
from app.db.models.user_session import UserSession


class UserSessionDAO(BaseDAO[UserSession]):
    model = UserSession