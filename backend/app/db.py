from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

# pool_pre_ping avoids "server closed the connection unexpectedly" errors
# from Supabase's pooler dropping idle connections.
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_db():
    """
    Yields a SQLAlchemy connection. Use as:
        with get_db() as db:
            db.execute(text("SELECT ..."), {...})
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_all(query: str, params: dict | None = None) -> list[dict]:
    with get_db() as db:
        result = db.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one(query: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: dict | None = None) -> None:
    with get_db() as db:
        db.execute(text(query), params or {})
