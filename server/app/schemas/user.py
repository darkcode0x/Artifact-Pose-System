from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.user import UserRole

class UserRead(BaseModel):
    user_id: str
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    
    # New profile fields
    full_name: str | None = None
    age: int | None = None
    email: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.operator
    full_name: str | None = None
    age: int | None = None
    email: str | None = None
    phone: str | None = None

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
