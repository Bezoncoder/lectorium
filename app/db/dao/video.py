from app.db.dao.base import BaseDAO
from app.db.models.video import Video


class VideoDAO(BaseDAO[Video]):
    model = Video