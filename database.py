from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

load_dotenv()
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ------------------ Dependencia DB ------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def unit_of_work(db: Session):
    """Context manager para asegurar transacciones ACID"""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise