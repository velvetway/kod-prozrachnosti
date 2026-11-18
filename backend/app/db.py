from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL, DATA_DIR


class Base(DeclarativeBase):
    pass


if DATABASE_URL.startswith("sqlite"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
