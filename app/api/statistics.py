from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.schemas.statistics import (
    VideoStatisticsPydantic,
    VideoViewerStatisticsPydantic,
)
from app.schemas.user import UserPydantic
from app.schemas.video import VideoPydantic
from app.services.video import StatisticsService, VideoService

router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
)


@router.get("")
async def statistics_index(
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    raw_statistics = await StatisticsService.get_all()

    current_user = UserPydantic.model_validate(raw_current_user)

    statistics = [
        VideoStatisticsPydantic.model_validate(dict(item))
        for item in raw_statistics
    ]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="statistics_index.html",
        context={
            "statistics": statistics,
            "current_user": current_user,
        },
    )


@router.get("/videos/{video_id}")
async def statistics_detail(
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

    raw_viewers = await StatisticsService.get_video_viewers(video_id)

    current_user = UserPydantic.model_validate(raw_current_user)
    video = VideoPydantic.model_validate(raw_video)

    viewers = [
        VideoViewerStatisticsPydantic.model_validate(dict(item))
        for item in raw_viewers
    ]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="statistics_detail.html",
        context={
            "video": video,
            "viewers": viewers,
            "current_user": current_user,
        },
    )