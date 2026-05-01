from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserCreate
from app.core.security import hash_password, verify_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])

class PasswordChangeRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

class UserUpdateRequest(BaseModel):
    current_username: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    age: int | None = None

@router.get("", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users

@router.get("/me", response_model=UserRead)
def get_my_profile(username: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/me", response_model=UserRead)
def update_my_profile(data: UserUpdateRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.current_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.full_name is not None: user.full_name = data.full_name
    if data.email is not None: user.email = data.email
    if data.phone is not None: user.phone = data.phone
    if data.age is not None: user.age = data.age
        
    db.commit()
    db.refresh(user)
    return user

@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        full_name=user_in.full_name,
        age=user_in.age,
        email=user_in.email,
        phone=user_in.phone,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/{user_id}", response_model=UserRead)
def get_user_by_id(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{user_id}/toggle-active", response_model=UserRead)
def toggle_user_active(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user

@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_user_password(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password("111111")
    db.commit()
    db.refresh(user)
    return user

@router.post("/change-password")
def change_password(data: PasswordChangeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
    
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True, "message": "Đổi mật khẩu thành công"}
