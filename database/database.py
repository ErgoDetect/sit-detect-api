from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Database URL: Ensure sensitive data is managed securely
DATABASE_URL = "postgresql://postgres:Admin1234@localhost/ergodb"

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Adds a connection pre-ping check for stale connections
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def get_db():
    """
    Dependency to get the database session.

    Yields:
        Session: SQLAlchemy session for database access.
    Closes:
        Closes the session after usage.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        # Add proper logging or handling of the error if needed
        db.rollback()  # Rollback transaction on error
        raise e  # Re-raise the error to the caller
    finally:
        db.close()  # Ensure the session is closed
