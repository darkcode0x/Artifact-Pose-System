from __future__ import annotations

import argparse

from app.core.database import SessionLocal, init_auth_database
from app.core.security import hash_password
from app.models.user import User


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
        if user is None:
            user = User(
                username=args.username,
                hashed_password=hash_password(args.password),
                role=args.role,
            )
            db.add(user)
            action = "created"
        else:
            user.hashed_password = hash_password(args.password)
            user.role = args.role
            action = "updated"

        db.commit()
        print(f"User '{args.username}' {action} successfully")
    finally:
        db.close()


if __name__ == "__main__":
    main()
