from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api import admin, catalog, orders
from app.api import config as public_config
from app.core.config import get_settings
from app.core.errors import _body, install_error_handlers
from app.core.storage import MAX_IMAGE_BYTES

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")
install_error_handlers(app)
MAX_BODY_BYTES = MAX_IMAGE_BYTES + 64 * 1024  # image cap plus multipart overhead


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    # Multipart bodies are parsed before auth runs, so reject oversized ones up front.
    # shortcut: trusts Content-Length; chunked bodies without it rely on the proxy's limit.
    if int(request.headers.get("content-length") or 0) > MAX_BODY_BYTES:
        return _body(413, "Request body is too large")
    return await call_next(request)


# Defence in depth: the DOM is built with textContent, this blocks the rest (framing, sniffing,
# foreign scripts, leaking the private order link via Referer).
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; connect-src 'self' https://*.supabase.co; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


for module in (catalog, public_config, admin, orders):
    app.include_router(module.router)

# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
