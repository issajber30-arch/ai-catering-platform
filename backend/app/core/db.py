import datetime as dt
import threading
import time
import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import JSON, DateTime, Engine, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.functions import now
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


class UtcDateTime(TypeDecorator):
    """timestamptz on Postgres; on SQLite (no time zones) stored as UTC and read back aware."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and dialect.name == "sqlite":
            if value.tzinfo is None:
                raise ValueError("naive datetime")  # same contract as the aware Postgres column
            value = value.astimezone(dt.UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and dialect.name == "sqlite":
            value = value.replace(tzinfo=dt.UTC)
        return value


Json = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {dt.datetime: UtcDateTime}


_seq_lock = threading.Lock()
_seq_last = 0


def _next_seq() -> int:
    # shortcut: stands in for Postgres identity columns on SQLite; unique and increasing within a
    # process and across restarts (clock-based); use Postgres for anything multi-process.
    global _seq_last
    with _seq_lock:
        _seq_last = max(_seq_last + 1, time.time_ns() // 1000)
        return _seq_last


def _sqlite_functions(conn, _record) -> None:
    """Give SQLite the Postgres functions the models' server defaults call."""
    conn.create_function("gen_random_uuid", 0, lambda: uuid.uuid4().hex)
    conn.create_function("now", 0, lambda: dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S.%f"))
    conn.create_function("next_seq", 0, _next_seq)
    conn.execute("PRAGMA foreign_keys=ON")


@compiles(now, "sqlite")
def _now_sqlite(_element, _compiler, **_kw) -> str:
    return "now()"  # SQLite's own CURRENT_TIMESTAMP has 1 s resolution; "newest first" needs more


def make_engine(url: str) -> Engine:
    if make_url(url).get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)
    # FastAPI runs sync endpoints in a threadpool, so connections cross threads.
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _sqlite_functions)
    return engine


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return make_engine(url)


def get_db() -> Iterator[Session]:
    with Session(get_engine()) as db:
        yield db


Db = Annotated[Session, Depends(get_db)]
