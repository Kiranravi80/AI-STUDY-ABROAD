"""MongoDB connection using Motor async driver."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings
import certifi

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global _client

    settings = get_settings()
    client_options = {"serverSelectionTimeoutMS": 10000}

    if settings.mongodb_url.startswith("mongodb+srv://") or "mongodb.net" in settings.mongodb_url:
        client_options.update({"tls": True, "tlsCAFile": certifi.where()})

    _client = AsyncIOMotorClient(settings.mongodb_url, **client_options)

    await _client.admin.command("ping")


async def close_db() -> None:
    global _client

    if _client:
        _client.close()
        _client = None


def get_database() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Database not connected.")

    return _client[get_settings().database_name]
