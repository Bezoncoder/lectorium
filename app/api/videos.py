from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.models.user import User, UserRole
from app.schemas.user import UserPydantic
from app.schemas.video import VideoPydantic
from app.schemas.video_view import VideoViewCreatePydantic
from app.services.video import VideoService

router = APIRouter(tags=["videos"])


@router.get(
    "/courses/{course_id}/videos",
    name="course_videos_list",
)
async def course_videos_list(
    course_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    stream = await VideoService.get_stream_for_user_course(
        user_id=current_user.id,
        course_id=course_id,
    )

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к видео этого курса",
        )

    raw_videos = await VideoService.get_all_for_stream(stream.id)

    videos = [
        VideoPydantic.model_validate(raw_video)
        for raw_video in raw_videos
    ]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="videos_list.html",
        context={
            "current_user": current_user,
            "course_id": course_id,
            "stream": stream,
            "videos": videos,
        },
    )


@router.get("/videos/{video_id}")
async def video_detail(
    video_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    raw_video = await VideoService.get_by_id_for_user(
        video_id=video_id,
        user_id=current_user.id,
    )

    if raw_video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено или недоступно",
        )

    video = VideoPydantic.model_validate(raw_video)

    view_stats = await VideoService.get_user_view_statistics(
        video_id=video_id,
        user_id=current_user.id,
    )

    if raw_current_user.role == UserRole.ADMIN:
        back_url = f"/admin/streams/{video.stream_id}/videos"
        back_label = "К видео потока"
    else:
        # У студента поток определяется сервером через его зачисление,
        # но кнопка возвращает именно к расписанию выбранного курса.
        stream = await VideoService.get_stream_for_user_course(
            user_id=current_user.id,
            course_id=(
                raw_video.stream.course_id
                if raw_video.stream is not None
                else 0
            ),
        )

        if stream is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому курсу",
            )

        back_url = f"/courses/{stream.course_id}"
        back_label = "К расписанию курса"

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="videos_detail.html",
        context={
            "video": video,
            "current_user": current_user,
            "view_stats": view_stats,
            "back_url": back_url,
            "back_label": back_label,
        },
    )


@router.get("/media/{video_id}", name="stream_video")
async def stream_video(
    video_id: int,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    raw_video = await VideoService.get_by_id_for_user(
        video_id=video_id,
        user_id=current_user.id,
    )

    if raw_video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено или недоступно",
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

    result = await VideoService.register_view(
        video_id=video_id,
        user_id=current_user.id,
        watched_seconds=payload.watched_seconds,
    )

    if result == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    if result == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому видео",
        )

    return None