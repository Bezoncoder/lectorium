from app.db.dao.base import BaseDAO
from app.db.models.user import User


class UserDAO(BaseDAO[User]):
    model = User