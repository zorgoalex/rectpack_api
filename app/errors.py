from typing import Any, Dict, Optional


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details


class ValidationError(ApiError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(422, "VALIDATION_ERROR", message, details)


class ConstraintError(ApiError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(400, "CONSTRAINT_ERROR", message, details)


class TimeoutError(ApiError):
    def __init__(self, message: str = "Time limit exceeded") -> None:
        super().__init__(408, "TIMEOUT", message)


class InternalError(ApiError):
    def __init__(self, message: str = "Internal error") -> None:
        super().__init__(500, "INTERNAL", message)


def error_payload(err: ApiError) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "status": "error",
        "error_code": err.error_code,
        "message": err.message,
    }
    if err.details is not None:
        payload["details"] = err.details
    return payload
