from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


def _load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

SERVER_ROOT = Path(__file__).resolve().parents[2]
_load_dotenv_file(SERVER_ROOT / ".env")

DEFAULT_AUTH_DB_PATH = SERVER_ROOT / "data" / "auth.db"
DEFAULT_AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv(
    "AUTH_DATABASE_URL",
    f"sqlite:///{DEFAULT_AUTH_DB_PATH.as_posix()}",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not DATABASE_URL.startswith("sqlite"),
)
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
