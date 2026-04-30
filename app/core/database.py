"""
Database Configuration
======================
SQLAlchemy engine, session factory, and base model for the notification DB.

Usage:
    from core.database import get_db, Base

    # In FastAPI endpoint:
    def my_endpoint(db: Session = Depends(get_db)):
        ...

    # In Celery task:
    with get_db_session() as db:
        ...
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import settings
from core.logging import get_logger

logger = get_logger("core.database")

# SQLAlchemy engine — lazy init to avoid import-time DB connection
_engine = None
_SessionLocal = None

Base = declarative_base()


def _init_engine():
    """Initialize the database engine (called once on first use)."""
    global _engine, _SessionLocal

    if _engine is not None:
        return

    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL not configured — DB features disabled")
        return

    _engine = create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    logger.info("Database engine initialized")


def get_db():
    """
    FastAPI dependency that yields a DB session.
    Automatically commits on success, rolls back on exception.
    """
    _init_engine()
    if _SessionLocal is None:
        yield None
        return

    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context manager for DB sessions in Celery tasks and non-FastAPI code.

    Usage:
        with get_db_session() as db:
            db.add(record)
    """
    _init_engine()
    if _SessionLocal is None:
        yield None
        return

    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all tables defined by Base.metadata (for initial setup / testing)."""
    _init_engine()
    if _engine is not None:
        Base.metadata.create_all(bind=_engine)
        logger.info("Database tables created")
