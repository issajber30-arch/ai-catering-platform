from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError

bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json")


def require_admin(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    supabase_url = get_settings().supabase_url
    if creds is None or not supabase_url:
        raise AppError(401, "Missing or invalid token")
    try:
        key = get_jwks_client().get_signing_key_from_jwt(creds.credentials).key
        claims = jwt.decode(
            creds.credentials,
            key,
            algorithms=["ES256", "RS256"],  # fixed list: never trust the token's own alg
            audience="authenticated",
            issuer=f"{supabase_url}/auth/v1",
            options={"require": ["exp", "aud", "iss"]},
        )
    except jwt.PyJWTError:
        raise AppError(401, "Missing or invalid token") from None
    if claims.get("app_metadata", {}).get("role") != "admin":
        raise AppError(403, "Admin role required")
    return claims
