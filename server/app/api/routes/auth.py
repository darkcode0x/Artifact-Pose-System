from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

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
