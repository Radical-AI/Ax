#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from __future__ import annotations

from collections.abc import Callable, Generator

from contextlib import contextmanager
from typing import Any, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, Session, sessionmaker


# some constants for database fields
HASH_FIELD_LENGTH: int = 32
NAME_OR_TYPE_FIELD_LENGTH: int = 100
LONG_STRING_FIELD_LENGTH: int = 255
JSON_FIELD_LENGTH: int = 4096

# by default, Text gets mapped to a TEXT field in MySQL is 2^16 - 1
# we use have MEDIUMTEXT and LONGTEXT in the MySQL db; in this case, use
# Text(MEDIUMTEXT_BYTES) or Text(LONGTEXT_BYTES). This is preferable to
# using MEDIUMTEXT and LONGTEXT directly because those are incompatible with
# SQLite that is used in unit tests.
MEDIUMTEXT_BYTES: int = 2**24 - 1
LONGTEXT_BYTES: int = 2**32 - 1

# global database variables
SESSION_FACTORY: Session | None = None

# set this to false to prevent SQLAlchemy for automatically expiring objects
# on commit, which essentially makes them unusable outside of a session
# see e.g. https://stackoverflow.com/a/50272761
EXPIRE_ON_COMMIT = False

T = TypeVar("T")


class SQABase:
    """Metaclass for SQLAlchemy classes corresponding to core Ax classes."""

    __allow_unmapped__ = True
    __table_args__ = {"extend_existing": True}
    pass


Base = declarative_base(cls=SQABase)


def create_mysql_engine_from_creator(
    creator: Callable,
    echo: bool = False,
    pool_recycle: int = 10,
    **kwargs: Any,
) -> Engine:
    """Create a SQLAlchemy engine with the MySQL dialect given a creator function.

    Args:
        creator:  a callable which returns a DBAPI connection.
        echo: if True, set engine to be verbose.
        pool_recycle: number of seconds after which to recycle
            connections. -1 means no timeout. Default is 10 seconds.
        **kwargs: keyword args passed to `create_engine`

    Returns:
        Engine: SQLAlchemy engine with connection to MySQL DB.

    """
    return create_engine(
        "mysql://", creator=creator, pool_recycle=pool_recycle, echo=echo, **kwargs
    )


def create_mysql_engine_from_url(
    url: str, echo: bool = False, pool_recycle: int = 10, **kwargs: Any
) -> Engine:
    """Create a SQLAlchemy engine with the MySQL dialect given a database url.

    Args:
        url: a database url that can include username, password, hostname, database name
            as well as optional keyword arguments for additional configuration.
            e.g. `dialect+driver://username:password@host:port/database`.
        echo: if True, set engine to be verbose.
        pool_recycle: number of seconds after which to recycle
            connections. -1 means no timeout. Default is 10 seconds.
        **kwargs: keyword args passed to `create_engine`

    Returns:
        Engine: SQLAlchemy engine with connection to MySQL DB.

    """
    return create_engine(url, pool_recycle=pool_recycle, echo=echo, **kwargs)


def create_test_engine(path: str | None = None, echo: bool = True) -> Engine:
    """Creates a SQLAlchemy engine object for use in unit tests.

    Args:
        path: if None, use in-memory SQLite; else
            attempt to create a SQLite DB in the path provided.
        echo: if True, set engine to be verbose.

    Returns:
        Engine: an instance of SQLAlchemy engine.

    """
    if path is None:
        # From SQLALchemy docs:
        # "To use a SQLite :memory: database, specify an empty URL:
        # `engine = create_engine('sqlite://')`"
        # (https://docs.sqlalchemy.org/en/14/core/engines.html#sqlite)
        db_path = "sqlite://"
    else:
        db_path = f"sqlite:///{path}"
    return create_engine(db_path, echo=echo)


def init_engine_and_session_factory(
    url: str | None = None,
    creator: Callable | None = None,
    echo: bool = False,
    force_init: bool = False,
    **kwargs: Any,
) -> None:
    """Initialize the global engine and SESSION_FACTORY for SQLAlchemy.

    The initialization needs to only happen once. Note that it is possible to
    re-initialize the engine by setting the `force_init` flag to True, but this
    should only be used if you are absolutely certain that you know what you
    are doing.

    Args:
        url: a database url that can include username, password, hostname, database name
            as well as optional keyword arguments for additional configuration.
            e.g. `dialect+driver://username:password@host:port/database`.
            Either this argument or `creator` argument must be specified.
        creator: a callable which returns a DBAPI connection.
            Either this argument or `url` argument must be specified.
        echo: if True, logging for engine is enabled.
        force_init: if True, allows re-initializing engine
            and session factory.
        **kwargs: keyword arguments passed to `create_mysql_engine_from_creator`

    """
    global SESSION_FACTORY

    if SESSION_FACTORY is not None:
        if force_init:
            SESSION_FACTORY.bind.dispose()
        else:
            return
    if url is not None:
        engine = create_mysql_engine_from_url(url=url, echo=echo, **kwargs)
    elif creator is not None:
        engine = create_mysql_engine_from_creator(creator=creator, echo=echo, **kwargs)
    else:
        raise ValueError("Must specify either `url` or `creator`.")
    SESSION_FACTORY = scoped_session(
        sessionmaker(bind=engine, expire_on_commit=EXPIRE_ON_COMMIT)
    )


def init_test_engine_and_session_factory(
    tier_or_path: str | None = None,
    echo: bool = False,
    force_init: bool = False,
    **kwargs: Any,
) -> None:
    """Initialize the global engine and SESSION_FACTORY for SQLAlchemy,
    using an in-memory SQLite database.

    The initialization needs to only happen once. Note that it is possible to
    re-initialize the engine by setting the `force_init` flag to True, but this
    should only be used if you are absolutely certain that you know what you
    are doing.

    Args:
        tier_or_path: the name of the DB tier.
        echo: if True, logging for engine is enabled.
        force_init: if True, allows re-initializing engine
            and session factory.
        **kwargs: keyword arguments passed to `create_mysql_engine_from_creator`

    """
    global SESSION_FACTORY

    if SESSION_FACTORY is not None:
        if force_init:
            SESSION_FACTORY.bind.dispose()
        else:
            return
    engine = create_test_engine(path=tier_or_path, echo=echo)
    create_all_tables(engine)

    SESSION_FACTORY = scoped_session(
        sessionmaker(bind=engine, expire_on_commit=EXPIRE_ON_COMMIT)
    )


def create_all_tables(engine: Engine) -> None:
    """Create all tables that inherit from Base.

    Args:
        engine: a SQLAlchemy engine with a connection to a MySQL
            or SQLite DB.

    Note:
        In order for all tables to be correctly created, all modules that
        define a mapped class that inherits from `Base` must be imported.

    """
    if engine.dialect.name == "mysql" and engine.dialect.default_schema_name == "ax":
        raise ValueError(
            "The open-source Ax table creation is likely not applicable in this case,"
            + "please contact the Adaptive Experimentation team if you need help."
        )
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Fetch a SQLAlchemy session with a connection to a DB.

    Returns:
        Session: an instance of a SQLAlchemy session.

    """
    global SESSION_FACTORY
    if SESSION_FACTORY is None:
        init_engine_and_session_factory()
    assert SESSION_FACTORY is not None
    # pyre-fixme[29]: `Session` is not a function.
    return SESSION_FACTORY()


def get_engine() -> Engine:
    """Fetch a SQLAlchemy engine, if already initialized.

    If not initialized, need to either call `init_engine_and_session_factory` or
    `get_session` explicitly.

    Returns:
        Engine: an instance of a SQLAlchemy engine with a connection to a DB.

    """
    global SESSION_FACTORY
    if SESSION_FACTORY is None:
        raise ValueError("Engine must be initialized first.")
    return SESSION_FACTORY.bind


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_context(
    url: str | None = None,
    creator: Callable | None = None,
    echo: bool = False,
    **kwargs: Any,
) -> Generator[None, None, None]:
    """
    Context manager that sets up a temporary session factory.

    Args:
        url: a database url that can include username, password, hostname, database name
            as well as optional keyword arguments for additional configuration.
            e.g. `dialect+driver://username:password@host:port/database`.
            Either this argument or `creator` argument must be specified.
        creator: a callable which returns a DBAPI connection.
            Either this argument or `url` argument must be specified.
        echo: if True, logging for engine is enabled.
        **kwargs: keyword arguments passed to `create_mysql_engine_from_creator`

    Yields:
        None
    """
    global SESSION_FACTORY

    # Preserve old session factory so we can restore it after the context manager
    old_session = SESSION_FACTORY

    # Create a new session factory for the test tier
    if url is not None:
        engine = create_mysql_engine_from_url(url=url, echo=echo, **kwargs)
    elif creator is not None:
        engine = create_mysql_engine_from_creator(creator=creator, echo=echo, **kwargs)
    else:
        raise ValueError("Must specify either `url` or `creator`.")

    # Overwrite the old session factory with a new one for the test tier
    session_factory = scoped_session(
        sessionmaker(bind=engine, expire_on_commit=EXPIRE_ON_COMMIT)
    )
    SESSION_FACTORY = session_factory

    try:
        yield
        session_factory.commit()
    except Exception:
        session_factory.rollback()
        raise
    finally:
        # Restore the old session factory
        session_factory.close()
        session_factory.bind.dispose()
        SESSION_FACTORY = old_session
