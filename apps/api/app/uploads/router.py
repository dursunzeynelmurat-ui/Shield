from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Upload, UploadStatus, User
from app.schemas import UploadOut
from app.uploads.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_SIZE_MB = 20


@router.post("", response_model=UploadOut, status_code=201)
async def create_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large (max {MAX_SIZE_MB}MB)")

    storage = get_storage()
    storage_url = await storage.save(content, file.filename or "upload", file.content_type)

    upload = Upload(
        user_id=current_user.id,
        file_type=file.content_type,
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
async def serve_file(key: str):
    """Serve locally stored files."""
    storage = get_storage()
    path = storage.get_local_path(f"local://{key}")
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(path))
