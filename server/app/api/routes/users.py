from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/v1/users")


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


# --------- Self-service endpoints (any authenticated user) ---------

@router.get("/me", response_model=UserRead)
def read_me(current: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current)


@router.patch("/me", response_model=UserRead)
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> UserRead:
    """User updates own profile (full_name, age, email, phone). Cannot change role here."""
    data = payload.model_dump(exclude_unset=True)
    if "role" in data:
        # Silently ignore role change attempts on /me to prevent privilege escalation.
        data.pop("role")
    if "password" in data and data["password"] is not None:
        current.password_hash = hash_password(data["password"])
        data.pop("password")
    for key, value in data.items():
        if value is not None:
            setattr(current, key, value)
    db.commit()
    db.refresh(current)
    return UserRead.model_validate(current)


@router.post("/me/change-password")
def change_my_password(
    data: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    if not verify_password(data.old_password, current.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
    current.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True, "message": "Đổi mật khẩu thành công"}


# --------- Admin endpoints ---------

@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserRead]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserRead.model_validate(u) for u in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        full_name=payload.full_name,
        age=payload.age,
        email=payload.email,
        phone=payload.phone,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> UserRead:
    """Admin can update any user; non-admin can only update self (without role change)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    is_admin = current.role == UserRole.admin
    is_self = current.user_id == user.user_id
    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail="Forbidden")

    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only admin can change role")
        user.role = data["role"]
    if "password" in data and data["password"] is not None:
        user.password_hash = hash_password(data["password"])
    for key in ("full_name", "age", "email", "phone"):
        if key in data and data[key] is not None:
            setattr(user, key, data[key])

    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> None:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.user_id == current.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(user)
    db.commit()


@router.patch("/{user_id}/toggle-active", response_model=UserRead)
def toggle_user_active(
    user_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> UserRead:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.user_id == current.user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_user_password(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password("111111")
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)
