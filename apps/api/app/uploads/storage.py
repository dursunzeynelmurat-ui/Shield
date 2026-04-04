"""Storage abstraction: local filesystem or S3-compatible."""
import os
import uuid
from pathlib import Path

from app.config import settings


class LocalStorage:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, filename: str, content_type: str) -> str:
        ext = Path(filename).suffix or ""
        key = f"{uuid.uuid4().hex}{ext}"
        dest = self.base_path / key
        dest.write_bytes(content)
        return f"local://{key}"

    async def get_url(self, storage_url: str) -> str:
        key = storage_url.removeprefix("local://")
        return f"/uploads/files/{key}"

    def get_local_path(self, storage_url: str) -> Path:
        key = storage_url.removeprefix("local://")
        return self.base_path / key


def get_storage() -> LocalStorage:
    # Could swap in S3Storage here based on settings.storage_backend
    return LocalStorage(settings.local_storage_path)
