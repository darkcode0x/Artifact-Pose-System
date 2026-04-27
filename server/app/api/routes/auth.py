from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserCreate, UserRead

router = APIRouter(prefix="/api/v1/auth")

_bearer = HTTPBearer(auto_error=False)


def _require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token bắt buộc")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
    username = payload.get("sub")
    role = payload.get("role")
    if not username or role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thực hiện thao tác này")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại")
    return user


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == data.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tai khoan")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Sai mat khau")

    token = create_access_token({"sub": user.username, "role": user.role})
    return LoginResponse(access_token=token, role=user.role)


@router.post("/register", response_model=UserRead, status_code=201)
def register_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
) -> UserRead:
    """Tạo user mới (chỉ admin)."""
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' đã tồn tại")
    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
) -> list[UserRead]:
    """Danh sách tất cả user (chỉ admin)."""
    return [UserRead.model_validate(u) for u in db.query(User).order_by(User.id).all()]


@router.delete("/users/{username}", status_code=204)
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
) -> None:
    """Xóa user (chỉ admin, không thể tự xóa mình)."""
    if username == admin.username:
        raise HTTPException(status_code=400, detail="Không thể tự xóa tài khoản đang đăng nhập")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User không tồn tại")
    db.delete(user)
    db.commit()
