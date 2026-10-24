"""
SQLite engine, sessions, time helpers and the schema upgrade.

Upgrade strategy: tables are created if missing, and any column that a model has but the
database lacks is added with ALTER TABLE ADD COLUMN. Nothing is ever dropped or rewritten,
so existing data survives every upgrade.
"""
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings
from .logging import log


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Naive UTC. Every timestamp in the database is UTC; the browser converts for display."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def parse_dt(value: str) -> datetime:
    """An ISO timestamp from the client, converted to naive UTC. Times without an offset are taken as UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def make_engine(url: str):
    eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(eng, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upgrade_schema(eng=None) -> None:
    from .. import models  # noqa: F401 - registers every table

    eng = eng or engine
    Base.metadata.create_all(eng)
    insp = inspect(eng)
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = col.type.compile(eng.dialect)
                default = ""
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    v = col.default.arg
                    default = f" DEFAULT {int(v) if isinstance(v, bool) else repr(v) if isinstance(v, str) else v}"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{default}'))
                log.info("schema upgrade: added %s.%s", table.name, col.name)
