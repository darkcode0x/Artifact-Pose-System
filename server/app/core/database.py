from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

SERVER_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTH_DB_PATH = SERVER_ROOT / "data" / "auth.db"
DEFAULT_AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv(
    "AUTH_DATABASE_URL",
    f"sqlite:///{DEFAULT_AUTH_DB_PATH.as_posix()}",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_auth_database() -> None:
    from app.models import user as _user  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
