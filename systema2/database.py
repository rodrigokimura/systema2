from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./systema2.db"

# check_same_thread=False is needed for SQLite + FastAPI threaded workers
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables. Import models here so SQLModel sees them."""
    from systema2 import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def init_db_if_local() -> None:
    """Initialize the DB only when not running as a pure HTTP client."""
    from systema2.config import Mode, get_mode

    if get_mode() is not Mode.CLIENT:
        init_db()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
