from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse

from app.core.dependencies import require_admin
from app.db.models.stream import StreamStatus
from app.db.models.user import User
from app.schemas.user import (
    AdminChangeStudentPasswordPydantic,
    AdminCreateStudentPydantic,
    AdminEnrollStudentPydantic,
    UserPydantic,
)
from app.schemas.video import VideoPydantic
from app.services.auth import UserService
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


def redirect_to(url: str) -> RedirectResponse:
    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/courses")
async def admin_courses_list(
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    courses = await ScheduleService.get_courses_for_admin()
    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_courses.html",
        context={
            "current_user": current_user,
            "courses": courses,
        },
    )


@router.get("/courses/new")
async def admin_course_create_page(
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_course_form.html",
        context={
            "current_user": current_user,
            "course": None,
        },
    )


@router.post("/courses")
async def admin_create_course(
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form()] = None,
    is_active: Annotated[bool, Form()] = True,
):
    course = await ScheduleService.create_course(
        title=title,
        description=description,
        is_active=is_active,
    )

    return redirect_to(f"/admin/courses/{course.id}")


@router.get("/courses/{course_id}")
async def admin_course_detail(
    course_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    course = await ScheduleService.get_course_with_streams(course_id)

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Курс не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_course_detail.html",
        context={
            "current_user": current_user,
            "course": course,
            "stream_statuses": list(StreamStatus),
        },
    )


@router.get("/courses/{course_id}/edit")
async def admin_course_edit_page(
    course_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    course = await ScheduleService.get_course_with_streams(course_id)

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Курс не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_course_form.html",
        context={
            "current_user": current_user,
            "course": course,
        },
    )


@router.post("/courses/{course_id}")
async def admin_update_course(
    course_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form()] = None,
    is_active: Annotated[bool, Form()] = True,
):
    course = await ScheduleService.update_course(
        course_id,
        title=title,
        description=description,
        is_active=is_active,
    )

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Курс не найден",
        )

    return redirect_to(f"/admin/courses/{course_id}")


@router.post("/courses/{course_id}/streams")
async def admin_create_stream(
    course_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    starts_on: Annotated[str | None, Form()] = None,
    ends_on: Annotated[str | None, Form()] = None,
    timezone: Annotated[str, Form(min_length=1, max_length=64)] = (
        "Europe/Moscow"
    ),
    telemost_url: Annotated[str | None, Form()] = None,
    stream_status: Annotated[str, Form()] = StreamStatus.DRAFT.value,
):
    try:
        stream = await ScheduleService.create_stream(
            course_id,
            title=title,
            starts_on=starts_on,
            ends_on=ends_on,
            timezone=timezone,
            telemost_url=telemost_url,
            status=stream_status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Курс не найден",
        )

    return redirect_to(f"/admin/streams/{stream.id}")


@router.get("/streams/{stream_id}")
async def admin_stream_detail(
    stream_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    stream, lessons, videos = (
        await ScheduleService.get_stream_admin_page_data(stream_id)
    )

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_stream.html",
        context={
            "current_user": current_user,
            "stream": stream,
            "lessons": lessons,
            "videos": [
                VideoPydantic.model_validate(video)
                for video in videos
            ],
            "stream_statuses": list(StreamStatus),
        },
    )


@router.post("/streams/{stream_id}")
async def admin_update_stream(
    stream_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    starts_on: Annotated[str | None, Form()] = None,
    ends_on: Annotated[str | None, Form()] = None,
    timezone: Annotated[str, Form(min_length=1, max_length=64)] = (
        "Europe/Moscow"
    ),
    telemost_url: Annotated[str | None, Form()] = None,
    stream_status: Annotated[str, Form()] = StreamStatus.DRAFT.value,
):
    try:
        stream = await ScheduleService.update_stream(
            stream_id,
            title=title,
            starts_on=starts_on,
            ends_on=ends_on,
            timezone=timezone,
            telemost_url=telemost_url,
            status=stream_status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    return redirect_to(f"/admin/streams/{stream_id}")


@router.post("/streams/{stream_id}/lessons")
async def admin_create_schedule_lesson(
    stream_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=500)],
    starts_at: Annotated[str, Form()],
    video_id: Annotated[str | None, Form()] = None,
):
    try:
        lesson = await ScheduleService.create_lesson(
            stream_id,
            title=title,
            starts_at=starts_at,
            video_id=video_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    return redirect_to(f"/admin/streams/{stream_id}")


@router.post("/streams/{stream_id}/lessons/{lesson_id}")
async def admin_update_schedule_lesson(
    stream_id: int,
    lesson_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=500)],
    starts_at: Annotated[str, Form()],
    video_id: Annotated[str | None, Form()] = None,
    sort_order: Annotated[int, Form(ge=0)] = 0,
):
    try:
        lesson = await ScheduleService.update_lesson(
            stream_id,
            lesson_id,
            title=title,
            starts_at=starts_at,
            video_id=video_id,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Занятие не найдено",
        )

    return redirect_to(f"/admin/streams/{stream_id}")


@router.post("/streams/{stream_id}/lessons/{lesson_id}/delete")
async def admin_delete_schedule_lesson(
    stream_id: int,
    lesson_id: int,
    _: Annotated[User, Depends(require_admin)],
):
    deleted = await ScheduleService.delete_lesson(
        stream_id,
        lesson_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Занятие не найдено",
        )

    return redirect_to(f"/admin/streams/{stream_id}")


@router.post("/streams/{stream_id}/schedule/clear")
async def admin_clear_schedule(
    stream_id: int,
    _: Annotated[User, Depends(require_admin)],
):
    cleared = await ScheduleService.clear_lessons(stream_id)

    if not cleared:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    return redirect_to(f"/admin/streams/{stream_id}")


@router.get("/streams/{stream_id}/videos")
async def admin_videos_list(
    stream_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    stream, _, raw_videos = (
        await ScheduleService.get_stream_admin_page_data(stream_id)
    )

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_videos_list.html",
        context={
            "current_user": current_user,
            "stream": stream,
            "videos": [
                VideoPydantic.model_validate(video)
                for video in raw_videos
            ],
        },
    )


@router.get("/streams/{stream_id}/videos/new")
async def create_video_page(
    stream_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    stream, _, _ = await ScheduleService.get_stream_admin_page_data(
        stream_id
    )

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_video_form.html",
        context={
            "current_user": current_user,
            "stream": stream,
            "video": None,
        },
    )


@router.post("/streams/{stream_id}/videos")
async def create_video(
    stream_id: int,
    raw_current_user: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form()] = None,
    video_file: UploadFile = File(...),
):
    stream, _, _ = await ScheduleService.get_stream_admin_page_data(
        stream_id
    )

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)

    (
        filename,
        original_filename,
        mime_type,
        size_bytes,
    ) = await save_video_file(video_file)

    try:
        await VideoService.create(
            stream_id=stream_id,
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

    return redirect_to(f"/admin/streams/{stream_id}/videos")


@router.get("/streams/{stream_id}/videos/{video_id}/edit")
async def edit_video_page(
    stream_id: int,
    video_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
):
    raw_video = await VideoService.get_by_id(video_id)

    if raw_video is None or raw_video.stream_id != stream_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    stream, _, _ = await ScheduleService.get_stream_admin_page_data(
        stream_id
    )

    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    current_user = UserPydantic.model_validate(raw_current_user)
    video = VideoPydantic.model_validate(raw_video)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_video_form.html",
        context={
            "current_user": current_user,
            "stream": stream,
            "video": video,
        },
    )


@router.post("/streams/{stream_id}/videos/{video_id}")
async def update_video(
    stream_id: int,
    video_id: int,
    _: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form()] = None,
):
    raw_video = await VideoService.get_by_id(video_id)

    if raw_video is None or raw_video.stream_id != stream_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    await VideoService.update(
        video_id=video_id,
        title=title.strip(),
        description=description.strip() if description else None,
    )

    return redirect_to(f"/admin/streams/{stream_id}/videos")


@router.post("/streams/{stream_id}/videos/{video_id}/delete")
async def delete_video(
    stream_id: int,
    video_id: int,
    _: Annotated[User, Depends(require_admin)],
):
    raw_video = await VideoService.get_by_id(video_id)

    if raw_video is None or raw_video.stream_id != stream_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео не найдено",
        )

    filename = await VideoService.delete(video_id)

    if filename is not None:
        await delete_video_file(filename)

    return redirect_to(f"/admin/streams/{stream_id}/videos")


@router.get("/students")
async def admin_students_page(
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
    login: str | None = Query(default=None, max_length=64),
):
    current_user = UserPydantic.model_validate(raw_current_user)
    student = None

    if login:
        student = await UserService.find_student_by_login(login)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_students.html",
        context={
            "current_user": current_user,
            "student": student,
            "query": login or "",
        },
    )


@router.get("/students/{user_id}")
async def admin_student_detail(
    user_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(require_admin)],
    error: str | None = Query(default=None),
    success: str | None = Query(default=None),
):
    student = await UserService.get_student_by_id(user_id)

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Студент не найден",
        )

    courses = await ScheduleService.get_courses_for_admin()
    current_user = UserPydantic.model_validate(raw_current_user)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin_student_detail.html",
        context={
            "current_user": current_user,
            "student": student,
            "courses": courses,
            "error": error,
            "success": success,
        },
    )

@router.post("/students/{user_id}/password/form")
async def admin_change_student_password_form(
    user_id: int,
    _: Annotated[User, Depends(require_admin)],
    password: Annotated[str, Form(min_length=8, max_length=72)],
):
    changed = await UserService.change_student_password(
        user_id=user_id,
        new_password=password,
    )

    if not changed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Студент не найден",
        )

    return redirect_to(f"/admin/students/{user_id}")


@router.post("/students/{user_id}/enroll/form")
async def admin_enroll_existing_student_form(
    user_id: int,
    _: Annotated[User, Depends(require_admin)],
    course_id: Annotated[int, Form(gt=0)],
    stream_id: Annotated[int | None, Form()] = None,
):
    try:
        await UserService.enroll_existing_student(
            user_id=user_id,
            course_id=course_id,
            stream_id=stream_id,
        )
    except ValueError as exc:
        message = str(exc).replace(" ", "+")
        return redirect_to(
            f"/admin/students/{user_id}"
            f"?error={message}"
        )

    return redirect_to(
        f"/admin/students/{user_id}"
        "?success=course_assigned"
    )

@router.post(
    "/api/students",
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_student_api(
    payload: AdminCreateStudentPydantic,
    _: Annotated[User, Depends(require_admin)],
):
    try:
        result = await UserService.create_student_and_enroll(
            login=payload.login,
            password=payload.password,
            course_id=payload.course_id,
            stream_id=payload.stream_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует",
        )

    return {
        "user": {
            "id": result.user.id,
            "login": result.user.login,
            "role": result.user.role.value,
        },
        "course": {
            "id": result.course.id,
            "title": result.course.title,
        },
        "stream": {
            "id": result.stream.id,
            "title": result.stream.title,
            "selection_source": (
                "auto"
                if result.stream_selected_automatically
                else "requested"
            ),
        },
        "enrollment": {
            "id": result.enrollment.id,
            "status": result.enrollment.status.value,
        },
    }


@router.post("/students/{user_id}/enroll")
async def admin_enroll_existing_student(
    user_id: int,
    payload: AdminEnrollStudentPydantic,
    _: Annotated[User, Depends(require_admin)],
):
    try:
        result = await UserService.enroll_existing_student(
            user_id=user_id,
            course_id=payload.course_id,
            stream_id=payload.stream_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Студент не найден",
        )

    return {
        "enrollment_id": result.enrollment.id,
        "course_id": result.course.id,
        "stream_id": result.stream.id,
        "stream_selected_automatically": (
            result.stream_selected_automatically
        ),
    }


@router.post("/students/{user_id}/password")
async def admin_change_student_password(
    user_id: int,
    payload: AdminChangeStudentPasswordPydantic,
    _: Annotated[User, Depends(require_admin)],
):
    changed = await UserService.change_student_password(
        user_id=user_id,
        new_password=payload.password,
    )

    if not changed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Студент не найден",
        )

    return {"status": "ok"}