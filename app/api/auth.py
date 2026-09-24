from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.schemas.user import UserPydantic
from app.services.auth import SessionService, UserService

router = APIRouter(tags=["auth"])


@router.get("/login")
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="auth_login.html",
        context={},
    )


@router.post("/login")
async def login(
    request: Request,
    login: Annotated[str, Form(min_length=3, max_length=64)],
    password: Annotated[str, Form(min_length=1, max_length=128)],
):
    raw_user = await UserService.authenticate(
        login=login,
        password=password,
    )

    if raw_user is None:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="auth_login.html",
            context={
                "error": "Неверный логин или пароль",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = UserPydantic.model_validate(raw_user)

    token = await SessionService.create(
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    response = RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
    )

    return response


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(settings.session_cookie_name)

    if token:
        await SessionService.delete(token)

    response = RedirectResponse(
        url="/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )

    return response