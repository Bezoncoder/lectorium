from app.db.dao.base import BaseDAO
from app.db.models.video_view import VideoView


class VideoViewDAO(BaseDAO[VideoView]):
    model = VideoView