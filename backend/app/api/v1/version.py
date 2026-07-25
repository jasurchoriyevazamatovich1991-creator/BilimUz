"""Version endpoint — lets clients (frontend, mobile, Telegram bot) detect
which API version they're talking to without parsing the OpenAPI schema."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.schemas import success_response

router = APIRouter(prefix="/version", tags=["Version"])

settings = get_settings()

APP_VERSION = "0.1.0"  # bump alongside docs/CHANGELOG.md entries


@router.get("")
def get_version():
    return success_response(
        {
            "app_name": settings.APP_NAME,
            "version": APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "api_prefix": settings.API_V1_PREFIX,
        },
        "Version info.",
    )
