import asyncio
import sys
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import settings
from .errors import ApiError, ConstraintError, ValidationError, error_payload, InternalError
from .models import ErrorResponse, OptimizeRequest, OptimizeResponse
from .packing import optimize


app = FastAPI(title=settings.service_name, version=settings.service_version)
JOB_SEMAPHORE = asyncio.Semaphore(settings.max_concurrent_jobs)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"}:
        limit = settings.max_body_bytes
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    err = ConstraintError("Request body too large")
                    return JSONResponse(status_code=err.status_code, content=error_payload(err))
            except ValueError:
                pass
        body = await request.body()
        if len(body) > limit:
            err = ConstraintError("Request body too large")
            return JSONResponse(status_code=err.status_code, content=error_payload(err))
        request._body = body
    return await call_next(request)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content=error_payload(exc))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    err = ValidationError("Request validation failed", details={"errors": exc.errors()})
    return JSONResponse(status_code=err.status_code, content=error_payload(err))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    err = InternalError()
    return JSONResponse(status_code=err.status_code, content=error_payload(err))


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    return {"status": "ok"}


@app.get("/version")
async def version() -> Dict[str, Any]:
    deps: Dict[str, str] = {}
    try:
        import fastapi

        deps["fastapi"] = getattr(fastapi, "__version__", "unknown")
    except Exception:
        deps["fastapi"] = "unknown"

    try:
        import rectpack

        deps["rectpack"] = getattr(rectpack, "__version__", "unknown")
    except Exception:
        deps["rectpack"] = "unknown"

    return {
        "service": {"name": settings.service_name, "version": settings.service_version},
        "python": sys.version,
        "dependencies": deps,
    }


@app.post("/v1/optimize", response_model=OptimizeResponse, responses={422: {"model": ErrorResponse}})
async def optimize_endpoint(payload: OptimizeRequest):
    async with JOB_SEMAPHORE:
        result = await asyncio.to_thread(optimize, payload)
        return result
