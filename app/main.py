from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import admin, auth, cabinet, statistics, videos
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.video_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=Path("app/static")),
    name="static",
)

app.state.templates = Jinja2Templates(
    directory=Path("app/templates"),
)

app.include_router(auth.router)
app.include_router(cabinet.router)
app.include_router(videos.router)
app.include_router(admin.router)
app.include_router(statistics.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    accept_header = request.headers.get("accept", "")

    is_html_request = "text/html" in accept_header
    is_api_request = request.url.path.startswith("/admin/api/")

    if (
        exc.status_code == status.HTTP_401_UNAUTHORIZED
        and is_html_request
        and not is_api_request
    ):
        response = RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )

        response.delete_cookie(
            key=settings.session_cookie_name,
            path="/",
        )

        return response

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
        },
    )


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}