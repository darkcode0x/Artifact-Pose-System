from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    role: UserRole = UserRole.OPERATOR


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: UserRole | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
