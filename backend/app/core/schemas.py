"""
The single response envelope every endpoint in the platform returns.
Routers build these via `success_response()` — never construct the dict
by hand, so the shape never drifts between modules.
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T | None = None
    errors: list[str] | None = None


def success_response(data: Any = None, message: str = "Operation completed successfully.") -> dict:
    return {"success": True, "message": message, "data": data, "errors": None}


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    meta: PaginationMeta
