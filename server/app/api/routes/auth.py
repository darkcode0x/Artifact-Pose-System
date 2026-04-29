from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import RegisterRequest, UserRead

router = APIRouter(prefix="/api/v1/auth")


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == data.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tai khoan")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Sai mat khau")

    token = create_access_token({"sub": user.username, "role": user.role})
    return LoginResponse(access_token=token, role=user.role)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> UserRead:
    """Public self-registration endpoint. Always creates role='user'."""
    existing = db.query(User).filter(User.username == data.username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role="user",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return UserRead.model_validate(user)