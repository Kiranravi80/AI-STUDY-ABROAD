"""Shared helper functions."""

from datetime import datetime, timezone
from typing import Any


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert MongoDB document _id to string id field."""
    if doc is None:
        return None
    result = dict(doc)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    return result


def serialize_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_doc(doc) for doc in docs if doc]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def paginate_params(page: int = 1, limit: int = 10) -> tuple[int, int]:
    """Return skip and limit values for MongoDB pagination."""
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    skip = (page - 1) * limit
    return skip, limit
