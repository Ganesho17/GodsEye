from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings

# If using default SQLite engine, enable multi-threaded read/write safety flags
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Initialize SQL engine connection pools
engine = create_engine(
    settings.DATABASE_URL, connect_args=connect_args
)

# Class builder yielding scoped transactional DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DeclarativeBase superclass mapping Python classes into SQL schemas
Base = declarative_base()

def get_db():
    """
    Yield-based scoped transactional database session dependency.
    Safely commits or rolls back session scopes and releases handles on conclusion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
