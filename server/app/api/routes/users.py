from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/v1/users")


@router.get("/me", response_model=UserRead)
def read_me(current: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current)


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserRead]:
    users = db.query(User).order_by(User.user_id.asc()).all()
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


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> UserRead:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    is_admin = current.role == UserRole.ADMIN
    is_self = current.user_id == user.user_id

    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only admin can change role")
        user.role = data["role"]
    if "password" in data and data["password"] is not None:
        if not (is_admin or is_self):
            raise HTTPException(
                status_code=403, detail="Only admin or owner can change password"
            )
        user.password_hash = hash_password(data["password"])

    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
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
    user_id: int,
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
    user_id: int,
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
