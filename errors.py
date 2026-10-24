"""One error type and one response envelope for the whole API."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import log


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, extra: dict | None = None):
        self.code, self.message, self.status, self.extra = code, message, status, extra or {}


def not_found(what: str) -> ApiError:
    return ApiError("NOT_FOUND", f"{what} not found.", 404)


def forbidden(message: str = "You don't have permission to do that.") -> ApiError:
    return ApiError("FORBIDDEN", message, 403)


def ok(data: Any = None) -> dict:
    return {"success": True, "data": data}


def _fail(code: str, message: str, status: int, extra: dict | None = None) -> JSONResponse:
    return JSONResponse({"success": False, "error": {"code": code, "message": message, **(extra or {})}}, status_code=status)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return _fail(e.code, e.message, e.status, e.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query"))
        return _fail("VALIDATION_ERROR", f"{where}: {first.get('msg', 'invalid input')}".strip(": "), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(e.status_code, "HTTP_ERROR")
        return _fail(code, str(e.detail), e.status_code)

    @app.exception_handler(Exception)
    async def _crash(request: Request, e: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _fail("INTERNAL_ERROR", "Something went wrong on our side.", 500)
