"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.v1.version import APP_VERSION
from app.core.config import get_settings, validate_production_secrets
from app.core.exceptions import AppException, app_exception_handler
from app.core.logging import configure_logging, get_logger
from app.core.middleware.security_headers import SecurityHeadersMiddleware

settings = get_settings()
configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=APP_VERSION,
    docs_url="/docs",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,   # never "*" — see .env.example
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
def on_startup() -> None:
    # Sprint 73 — SEC-1. Fail fast rather than boot a production instance
    # that is silently signing JWTs (or storing "encrypted" secrets) with
    # a public, repository-visible default value — see
    # core/config.validate_production_secrets() for the full rationale.
    unsafe = validate_production_secrets(settings)
    if unsafe:
        # Sprint 81 — Package 1 (S81-AUDIT-004): message now names the
        # actual guarded environment (ENVIRONMENT can be "staging" here
        # too, not only "production") instead of hardcoding "production"
        # — the secret names themselves are never included in `unsafe`,
        # only their field NAMES, so this never logs/raises an actual
        # secret value.
        raise RuntimeError(
            f"Refusing to start in {settings.ENVIRONMENT!r} with unsafe default secret(s): "
            f"{', '.join(unsafe)}. Set real values via environment variables/.env before starting."
        )
    logger.info(f"{settings.APP_NAME} v{APP_VERSION} starting in {settings.ENVIRONMENT} mode")
