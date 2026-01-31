from dataclasses import dataclass
import os


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None else default


@dataclass(frozen=True)
class Settings:
    service_name: str = "rectpack"
    service_version: str = "0.1.0"
    port: int = _get_int("PORT", 8080)
    log_level: str = _get_str("LOG_LEVEL", "info")
    max_body_bytes: int = _get_int("MAX_BODY_BYTES", 5 * 1024 * 1024)
    max_instances: int = _get_int("MAX_INSTANCES", 5000)
    default_time_limit_ms: int = _get_int("DEFAULT_TIME_LIMIT_MS", 800)
    default_restarts: int = _get_int("DEFAULT_RESTARTS", 5)
    max_concurrent_jobs: int = _get_int("MAX_CONCURRENT_JOBS", 1)
    default_unit_scale: int = _get_int("DEFAULT_UNIT_SCALE", 100)


settings = Settings()
