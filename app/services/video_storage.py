from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


ALLOWED_VIDEO_TYPES: dict[str, set[str]] = {
    "video/mp4": {".mp4"},
    "video/webm": {".webm"},
    "video/ogg": {".ogv", ".ogg"},
}

CHUNK_SIZE = 1024 * 1024


async def save_video_file(
    upload: UploadFile,
) -> tuple[str, str, str, int]:
    original_filename = Path(upload.filename or "video").name
    suffix = Path(original_filename).suffix.lower()

    allowed_extensions = ALLOWED_VIDEO_TYPES.get(
        upload.content_type or "",
    )

    if not allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются MP4, WebM и OGG",
        )

    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Расширение файла не соответствует Content-Type",
        )

    settings.video_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}{suffix}"
    target_path = settings.video_dir / stored_filename
    size_bytes = 0

    try:
        async with aiofiles.open(target_path, "wb") as output_file:
            while chunk := await upload.read(CHUNK_SIZE):
                size_bytes += len(chunk)

                if size_bytes > settings.max_video_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            "Размер файла превышает "
                            f"{settings.max_video_size_mb} MB"
                        ),
                    )

                await output_file.write(chunk)

    except Exception:
        target_path.unlink(missing_ok=True)
        raise

    finally:
        await upload.close()

    return (
        stored_filename,
        original_filename,
        upload.content_type or "application/octet-stream",
        size_bytes,
    )


async def delete_video_file(filename: str) -> None:
    (settings.video_dir / filename).unlink(missing_ok=True)