from __future__ import annotations
from app.core.database import SessionLocal
from app.models.user import User

def main() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print("\n" + "="*50)
        print(f"{'ID':<5} | {'Username':<15} | {'Role':<15}")
        print("-" * 50)
        for user in users:
            print(f"{user.id:<5} | {user.username:<15} | {user.role:<15}")
        print("="*50 + "\n")
    finally:
        db.close()

if __name__ == "__main__":
    main()
