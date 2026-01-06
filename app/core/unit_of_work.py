from sqlalchemy.orm import Session
from contextlib import contextmanager

@contextmanager
def unit_of_work(db: Session):
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
def get_db_session(db: Session) -> Session:
    return db