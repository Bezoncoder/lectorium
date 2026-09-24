from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.dependencies import get_current_user
from app.db.models.user import User, UserRole
from app.schemas.user import UserPydantic
from app.services.cabinet import CabinetService
from app.services.schedule import ScheduleService

router = APIRouter(tags=["cabinet"])


@router.get("/", name="cabinet")
async def cabinet_index(
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    if raw_current_user.role == UserRole.ADMIN:
        courses = await ScheduleService.get_courses_for_admin()

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="cabinet.html",
            context={
                "current_user": current_user,
                "admin_courses": courses,
                "course_cards": [],
            },
        )

    course_cards = await CabinetService.get_my_courses(
        user_id=current_user.id,
    )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="cabinet.html",
        context={
            "current_user": current_user,
            "admin_courses": [],
            "course_cards": course_cards,
        },
    )


@router.get("/courses/{course_id}", name="course_cabinet")
async def course_cabinet(
    course_id: int,
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    if raw_current_user.role == UserRole.ADMIN:
        course = await ScheduleService.get_course_with_streams(course_id)

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Курс не найден",
            )

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="cabinet.html",
            context={
                "current_user": current_user,
                "admin_courses": [course],
                "course_cards": [],
                "selected_admin_course": course,
            },
        )

    dashboard = await CabinetService.get_course_dashboard(
        user_id=current_user.id,
        course_id=course_id,
    )

    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому курсу",
        )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="course_dashboard.html",
        context={
            "current_user": current_user,
            "course": dashboard.course,
            "stream": dashboard.stream,
            "lessons": dashboard.lessons,
            "next_lesson": dashboard.next_lesson,
            "progress": dashboard.progress,
        },
    )