"""Authentication routes: register, login, refresh, password reset."""

from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId

from app.database import get_database
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    PasswordResetRequest,
    UserResponse,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.utils.helpers import serialize_doc, utc_now
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _build_token_response(user: dict) -> TokenResponse:
    user_id = str(user["_id"])
    token_data = {"sub": user_id, "role": user["role"], "email": user["email"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        role=user["role"],
        user_id=user_id,
        email=user["email"],
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_student(data: UserRegister):
    """Students can self-register. Employees and admins cannot."""
    db = get_database()

    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "email": data.email.lower(),
        "password": hash_password(data.password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": "student",
        "is_active": True,
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }

    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    # Create empty profile for the student
    await db.profiles.insert_one({
        "user_id": str(result.inserted_id),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "completion_percentage": 10,
        "created_at": utc_now().isoformat(),
    })

    return await _build_token_response(user_doc)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin):
    """Login for all roles."""
    db = get_database()
    user = await db.users.find_one({"email": data.email.lower()})

    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return await _build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest):
    """Get new access token using refresh token."""
    payload = decode_refresh_token(data.refresh_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="User not found")

    return await _build_token_response(user)


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Return current authenticated user."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        role=user["role"],
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )


@router.post("/password-reset-request")
async def password_reset_request(data: PasswordResetRequest):
    """Request password reset (sends token - in production, send via email)."""
    db = get_database()
    user = await db.users.find_one({"email": data.email.lower()})

    # Always return success to prevent email enumeration
    if user:
        reset_token = create_access_token(
            {"sub": str(user["_id"]), "purpose": "password_reset"},
        )
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"reset_token": reset_token, "updated_at": utc_now().isoformat()}},
        )

    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Logout - client should clear tokens."""
    return {"message": "Logged out successfully"}
