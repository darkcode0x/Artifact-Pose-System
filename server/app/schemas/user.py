from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["admin", "operator", "user"]


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    role: UserRole = "user"


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: UserRole | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)