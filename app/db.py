from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, future=True)


def build_session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False, future=True)
