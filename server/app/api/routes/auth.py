from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import RegisterRequest, UserRead

router = APIRouter(prefix="/api/v1/auth")


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == data.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tai khoan")

    # Changed from user.hashed_password to user.password_hash
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Sai mat khau")

    role_value = user.role.value if isinstance(user.role, UserRole) else user.role
    token = create_access_token({"sub": user.username, "role": role_value})
    return LoginResponse(access_token=token, role=role_value)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> UserRead:
    """Public self-registration endpoint. Always creates role=operator."""
    existing = db.query(User).filter(User.username == data.username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=UserRole.operator,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return UserRead.model_validate(user)