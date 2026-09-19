from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.schemas.user import UserPydantic
from app.schemas.video import VideoPydantic
from app.schemas.video_view import VideoViewCreatePydantic
from app.services.video import VideoService

router = APIRouter(tags=["videos"])


@router.get("/videos", name="videos_list")
async def videos_list(
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    raw_videos = await VideoService.get_all()

    current_user = UserPydantic.model_validate(raw_current_user)

    videos = [
        VideoPydantic.model_validate(raw_video)
        for raw_video in raw_videos
    ]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="videos_list.html",
        context={
            "videos": videos,
            "current_user": current_user,
        },
    )


@router.get("/videos/{video_id}")
async def video_detail(
    video_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    raw_video = await VideoService.get_by_id(video_id)

    if raw_video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    current_user = UserPydantic.model_validate(raw_current_user)
    video = VideoPydantic.model_validate(raw_video)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="videos_detail.html",
        context={
            "video": video,
            "current_user": current_user,
        },
    )


@router.get("/media/{video_id}", name="stream_video")
async def stream_video(
    video_id: int,
    _: Annotated[User, Depends(get_current_user)],
):
    raw_video = await VideoService.get_by_id(video_id)

    if raw_video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    video = VideoPydantic.model_validate(raw_video)
    file_path = Path(settings.video_dir) / video.filename

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл видео не найден",
        )

    return FileResponse(
        path=file_path,
        media_type=video.mime_type,
        filename=video.original_filename,
        content_disposition_type="inline",
    )


@router.post(
    "/videos/{video_id}/view",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def register_video_view(
    video_id: int,
    payload: VideoViewCreatePydantic,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    registered = await VideoService.register_view(
        video_id=video_id,
        user_id=current_user.id,
        watched_seconds=payload.watched_seconds,
    )

    if not registered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    return None