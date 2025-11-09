"""
Database connection management

Handles SQLAlchemy session creation and database initialization.
"""

import os
import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .schema import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions.

    Supports both SQLite (development) and PostgreSQL (production).
    """

    def __init__(self, database_url: str = None):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL. If None, uses environment variable
                         DB_URL or defaults to SQLite at data/insider_trades.db
        """
        if database_url is None:
            database_url = os.getenv('DB_URL')

        if database_url is None:
            # Default to SQLite
            db_path = Path('./data/insider_trades.db')
            db_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f'sqlite:///{db_path}'
            logger.info(f"Using SQLite database at {db_path}")

        self.database_url = database_url
        self.is_sqlite = database_url.startswith('sqlite')

        # Create engine
        if self.is_sqlite:
            # SQLite-specific settings
            self.engine = create_engine(
                database_url,
                connect_args={'check_same_thread': False},
                poolclass=StaticPool,
                echo=False  # Set to True for SQL query logging
            )
        else:
            # PostgreSQL or other databases
            self.engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                echo=False
            )

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info(f"Database connection initialized: {database_url.split('@')[-1]}")

    def init_db(self):
        """
        Create all database tables.

        This is idempotent - safe to call multiple times.
        """
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")

    def drop_db(self):
        """
        Drop all database tables.

        WARNING: This will delete all data!
        """
        logger.warning("Dropping all database tables!")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("Database tables dropped")

    def get_session(self) -> Session:
        """
        Get a new database session.

        Returns:
            SQLAlchemy Session object

        Usage:
            session = db_manager.get_session()
            try:
                # Use session
                session.add(obj)
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        """
        return self.SessionLocal()

    def get_session_context(self) -> Generator[Session, None, None]:
        """
        Get a database session as a context manager.

        Yields:
            SQLAlchemy Session object

        Usage:
            with db_manager.get_session_context() as session:
                # Use session
                session.add(obj)
                session.commit()
        """
        session = self.SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global database manager instance
_db_manager = None


def get_db_manager(database_url: str = None) -> DatabaseManager:
    """
    Get the global database manager instance.

    Args:
        database_url: Database URL (only used on first call)

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url)
    return _db_manager


def get_session() -> Session:
    """
    Convenience function to get a database session.

    Returns:
        SQLAlchemy Session object
    """
    return get_db_manager().get_session()


def init_db(database_url: str = None):
    """
    Initialize database tables.

    Args:
        database_url: Database URL (optional)
    """
    db_manager = get_db_manager(database_url)
    db_manager.init_db()
