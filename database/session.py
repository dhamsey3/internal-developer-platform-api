from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from database.models import Base


connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_deployment_columns() -> None:
    inspector = inspect(engine)
    if "deployments" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("deployments")}
    dialect = engine.dialect.name
    column_definitions = {
        "container_port": "INTEGER",
        "expires_at": "TIMESTAMP" if dialect != "sqlite" else "DATETIME",
        "is_sandbox": "BOOLEAN NOT NULL DEFAULT 0" if dialect == "sqlite" else "BOOLEAN NOT NULL DEFAULT false",
    }
    with engine.begin() as connection:
        for name, definition in column_definitions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE deployments ADD COLUMN {name} {definition}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_deployment_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
