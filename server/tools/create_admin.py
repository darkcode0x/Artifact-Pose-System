from __future__ import annotations

import argparse

from app.core.database import SessionLocal, init_auth_database
from app.core.security import hash_password
from app.models.user import User, UserRole


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update an admin user")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--role", default="admin")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_auth_database()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        
        # Determine the role enum
        try:
            role_enum = UserRole(args.role.lower())
        except ValueError:
            role_enum = UserRole.ADMIN if args.role.lower() == "admin" else UserRole.OPERATOR

        if user is None:
            user = User(
                username=args.username,
                password_hash=hash_password(args.password),
                role=role_enum,
            )
            db.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(args.password)
            user.role = role_enum
            action = "updated"

        db.commit()
        print(f"User '{args.username}' {action} successfully")
    finally:
        db.close()


if __name__ == "__main__":
    main()
