from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SessionType, sessionmaker

from app.core.config.config import settings


def _database_url() -> str:
    db_path = Path(settings.DB_PATH)
    if not db_path.is_absolute():
        db_path = Path(__file__).parent.parent.parent.parent / db_path
    return f"sqlite:///{db_path}"


engine = create_engine(
    _database_url(),
    echo=False,
    connect_args={"check_same_thread": False},
)
_Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def getSession():
    session = _Session()
    try:
        yield session
    finally:
        session.close()


def getStaticSession() -> SessionType:
    return _Session()


def init_db() -> None:
    from app.models.base_model import Base
    from app.models.export_model import EXPORT_MODEL  # noqa: F401
    from app.models.job_model import JOB_MODEL        # noqa: F401

    Base.metadata.create_all(bind=engine)
