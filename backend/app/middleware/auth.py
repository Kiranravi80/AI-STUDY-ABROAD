"""Authentication middleware and dependency injection."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import get_database
from app.utils.security import decode_access_token
from app.utils.helpers import serialize_doc
from bson import ObjectId

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Validate JWT and return the current user document."""
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})

    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return serialize_doc(user)


def require_roles(*roles: str):
    """Factory for role-based access control dependencies."""

    async def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(roles)}",
            )
        return user

    return role_checker


# Convenience role dependencies
require_student = require_roles("student")
require_employee = require_roles("employee")
require_admin = require_roles("admin")
require_employee_or_admin = require_roles("employee", "admin")
