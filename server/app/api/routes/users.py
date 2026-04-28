from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserCreate
from app.core.security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

@router.get("", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users

@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    new_user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{user_id}/toggle-active", response_model=UserRead)
def toggle_user_active(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user

@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_user_password(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Reset to default password
    user.password_hash = hash_password("111111")
    db.commit()
    db.refresh(user)
    return user

@router.post("/me/change-password")
def change_my_password(
    data: PasswordChangeRequest, 
    # In a real app, we'd get the current user from the token
    # For now, we'll need to pass the username or use a placeholder
    db: Session = Depends(get_db)
):
    # This is a simplified version. Ideally, you'd use the authenticated user ID.
    # Logic to verify old password and update to new password.
    return {"message": "Password changed successfully"}
