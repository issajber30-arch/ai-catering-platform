from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

CODES = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    502: "bad_gateway",
    503: "unavailable",
}


class AppError(Exception):
    def __init__(
        self, status: int, message: str, details: dict | None = None, code: str | None = None
    ):
        self.status, self.message, self.details, self.code = status, message, details or {}, code


def _body(
    status: int, message: str, details: dict | None = None, headers=None, code: str | None = None
) -> JSONResponse:
    error = {
        "code": code or CODES.get(status, "error"),
        "message": message,
        "details": details or {},
    }
    return JSONResponse({"error": error}, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _body(exc.status, exc.message, exc.details, code=exc.code)

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError):
        # e.g. deleting a dish or zone that an order still references
        return _body(409, "Record is referenced by other records")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return _body(exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        # Input values are dropped on purpose so large or private data is not echoed back.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return _body(422, "Invalid request", {"errors": errors})
