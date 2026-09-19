from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.schemas.user import UserPydantic
from app.services.cabinet import CabinetService


router = APIRouter(tags=["cabinet"])


@router.get("/", name="cabinet")
async def cabinet_index(
    request: Request,
    raw_current_user: Annotated[User, Depends(get_current_user)],
):
    current_user = UserPydantic.model_validate(raw_current_user)

    dashboard = await CabinetService.get_dashboard(
        user_id=current_user.id,
    )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="cabinet.html",
        context={
            "current_user": current_user,
            "course": dashboard.course,
            "lessons": dashboard.lessons,
            "next_lesson": dashboard.next_lesson,
            "progress": dashboard.progress,
        },
    )