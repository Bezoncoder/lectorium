from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse

from app.core.dependencies import require_admin
from app.db.models.user import User
from app.schemas.user import UserPydantic
from app.schemas.video import VideoPydantic
from app.services.schedule import ScheduleService
from app.services.video import VideoService
from app.services.video_storage import (
    delete_video_file,
    save_video_file,
)


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get("/videos")
async def admin_videos_list(
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    raw_videos = await VideoService.get_all()

    current_user = UserPydantic.model_validate(raw_current_user)

    videos = [
        VideoPydantic.model_validate(raw_video)
        for raw_video in raw_videos
    ]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_videos_list.html",
        context={
            "videos": videos,
            "current_user": current_user,
        },
    )


@router.get("/videos/new")
async def create_video_page(
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_video_form.html",
        context={
            "video": None,
            "current_user": current_user,
        },
    )


@router.post("/videos")
async def create_video(
    raw_current_user: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form()] = None,
    video_file: UploadFile = File(...),
):
    current_user = UserPydantic.model_validate(raw_current_user)

    (
        filename,
        original_filename,
        mime_type,
        size_bytes,
    ) = await save_video_file(video_file)

    try:
        await VideoService.create(
            title=title.strip(),
            description=description.strip() if description else None,
            filename=filename,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            uploaded_by_id=current_user.id,
        )
    except Exception:
        await delete_video_file(filename)
        raise

    return RedirectResponse(
        url="/admin/videos",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/videos/{video_id}/edit")
async def edit_video_page(
    video_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
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
        name="admin_video_form.html",
        context={
            "video": video,
            "current_user": current_user,
        },
    )


@router.post("/videos/{video_id}")
async def update_video(
    video_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form()] = None,
):
    raw_video = await VideoService.update(
        video_id=video_id,
        title=title.strip(),
        description=description.strip() if description else None,
    )

    if raw_video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    return RedirectResponse(
        url="/admin/videos",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/videos/{video_id}/delete")
async def delete_video(
    video_id: int,
    _: Annotated[User, Depends(require_admin)],
):
    filename = await VideoService.delete(video_id)

    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    await delete_video_file(filename)

    return RedirectResponse(
        url="/admin/videos",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/schedule")
async def admin_schedule_page(
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    (
        raw_course,
        raw_lessons,
        raw_videos,
    ) = await ScheduleService.get_admin_page_data()

    if raw_course is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Курс не найден. "
                "Проверьте, что миграция расписания применена."
            ),
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    videos = [
        VideoPydantic.model_validate(raw_video)
        for raw_video in raw_videos
    ]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_schedule.html",
        context={
            "current_user": current_user,
            "course": raw_course,
            "lessons": raw_lessons,
            "videos": videos,
        },
    )


@router.post("/schedule/course")
async def admin_update_course(
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    dates: Annotated[str, Form(min_length=1, max_length=255)],
    timezone: Annotated[str, Form(min_length=1, max_length=64)],
    telemost_url: Annotated[str | None, Form()] = None,
):
    course = await ScheduleService.update_course(
        title=title,
        dates=dates,
        timezone=timezone,
        telemost_url=telemost_url,
    )

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Курс не найден",
        )

    return RedirectResponse(
        url="/admin/schedule",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/schedule/lessons")
async def admin_create_schedule_lesson(
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=500)],
    starts_at: Annotated[str, Form()],
    video_id: Annotated[str | None, Form()] = None,
):
    lesson = await ScheduleService.create_lesson(
        title=title,
        starts_at=starts_at,
        video_id=video_id,
    )

    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Курс не найден",
        )

    return RedirectResponse(
        url="/admin/schedule",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/schedule/lessons/{lesson_id}")
async def admin_update_schedule_lesson(
    lesson_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=500)],
    starts_at: Annotated[str, Form()],
    video_id: Annotated[str | None, Form()] = None,
    sort_order: Annotated[int, Form(ge=0)] = 0,
):
    lesson = await ScheduleService.update_lesson(
        lesson_id,
        title=title,
        starts_at=starts_at,
        video_id=video_id,
        sort_order=sort_order,
    )

    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Занятие не найдено",
        )

    return RedirectResponse(
        url="/admin/schedule",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/schedule/lessons/{lesson_id}/delete")
async def admin_delete_schedule_lesson(
    lesson_id: int,
    _: Annotated[User, Depends(require_admin)],
):
    deleted = await ScheduleService.delete_lesson(lesson_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Занятие не найдено",
        )

    return RedirectResponse(
        url="/admin/schedule",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/schedule/clear")
async def admin_clear_schedule(
    _: Annotated[User, Depends(require_admin)],
):
    cleared = await ScheduleService.clear_lessons()

    if not cleared:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Курс не найден",
        )

    return RedirectResponse(
        url="/admin/schedule",
        status_code=status.HTTP_303_SEE_OTHER,
    )