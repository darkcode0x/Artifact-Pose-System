from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from app.core.database import Base

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"

class User(Base):
    __tablename__ = "users" # Quoted "user" in SQL, but "users" is safer in SQLAlchemy to avoid conflicts

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
