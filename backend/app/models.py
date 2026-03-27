"""
SQLAlchemy models and database setup for DePredict.
"""

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from .config import Config

_db_path = os.path.join(Config.PROJECT_ROOT, "backend", "data", "depredict.db")
_db_url = f"sqlite:///{_db_path}"

engine = create_engine(_db_url, echo=False, pool_pre_ping=True)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    tier = Column(String, default="free", nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    predictions_this_month = Column(Integer, default=0, nullable=False)
    predictions_reset_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    Base.metadata.create_all(engine)
