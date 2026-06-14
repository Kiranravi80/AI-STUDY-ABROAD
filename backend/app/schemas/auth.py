"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr, Field
from typing import Literal


Role = Literal["student", "employee", "admin"]


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: Role
    user_id: str
    email: str
    first_name: str
    last_name: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: Role
    is_active: bool = True
    created_at: str | None = None
