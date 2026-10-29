import uuid

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
# Detected from magic bytes, never from the client's filename or content type.
_EXT = {"jpeg": "jpg", "png": "png", "webp": "webp"}
_TYPES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def detect_image(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def upload_to_supabase(data: bytes, kind: str) -> str:
    """Upload to the public bucket with a server-generated name; returns the object path."""
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_role_key):
        raise AppError(503, "Storage is not configured")
    name = f"{uuid.uuid4()}.{_EXT[kind]}"
    response = httpx.post(
        f"{s.supabase_url}/storage/v1/object/{s.storage_bucket}/{name}",
        content=data,
        headers={
            "Authorization": f"Bearer {s.supabase_service_role_key}",
            "Content-Type": _TYPES[kind],
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise AppError(502, "Image upload failed")
    return name


def get_uploader():
    return upload_to_supabase
