from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Upload, UploadStatus, User
from app.schemas import UploadOut
from app.uploads.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_SIZE_MB = 20

# Magic byte signatures for MIME validation (avoids content-type spoofing)
_MAGIC: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),   # webp: RIFF????WEBP
    (b"%PDF", "application/pdf"),
]


def _detect_mime(content: bytes) -> str | None:
    for magic, mime in _MAGIC:
        if content[:len(magic)] == magic:
            if mime == "image/webp":
                # Extra check: bytes 8-12 must be b"WEBP"
                return mime if content[8:12] == b"WEBP" else None
            return mime
    return None


@router.post("", response_model=UploadOut, status_code=201)
async def create_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large (max {MAX_SIZE_MB}MB)")

    detected = _detect_mime(content)
    if detected not in ALLOWED_TYPES:
        raise HTTPException(400, "Unsupported or unrecognised file type")

    storage = get_storage()
    storage_url = await storage.save(content, file.filename or "upload", detected)

    upload = Upload(
        user_id=current_user.id,
        file_type=detected,
        storage_url=storage_url,
        original_filename=file.filename,
        file_size=len(content),
        status=UploadStatus.pending,
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return upload


@router.get("/{upload_id}", response_model=UploadOut)
async def get_upload(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    result = await db.execute(select(Upload).where(Upload.id == upload_id, Upload.user_id == current_user.id))
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(404, "Upload not found")
    return upload


@router.get("/files/{key}")
async def serve_file(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve locally stored files — only to the owning user."""
    from sqlalchemy import select
    storage = get_storage()
    try:
        path = storage.get_local_path(f"local://{key}")
    except ValueError:
        raise HTTPException(400, "Invalid file key")

    # Verify ownership: find an upload with this storage URL belonging to current user
    result = await db.execute(
        select(Upload).where(
            Upload.storage_url == f"local://{key}",
            Upload.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "File not found")

    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(path))
