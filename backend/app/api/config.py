from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api")


@router.get("/public-config")
def public_config() -> dict:
    s = get_settings()
    return {"supabase_url": s.supabase_url, "supabase_anon_key": s.supabase_anon_key}
