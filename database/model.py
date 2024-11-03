import uuid
from sqlalchemy import (
    Column,
    DateTime,
    String,
    ForeignKey,
    Boolean,
    UniqueConstraint,
    JSON,
    Integer,
)
from sqlalchemy.orm import relationship
from auth.token import get_current_time
from database.database import Base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(21), primary_key=True, index=True)
    email = Column(String(100), unique=False, nullable=False)
    display_name = Column(String(100), nullable=False)
    sign_up_method = Column(String(50), nullable=True)
    type = Column(String(50))  # Discriminator column

    # Define the relationship with UserSession
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "user"}


class EmailUser(User):
    __tablename__ = "email_users"
    user_id = Column(String(21), ForeignKey("users.user_id"), primary_key=True)
    password = Column(String(128), nullable=False)
    verified = Column(Boolean, default=False)

    __mapper_args__ = {"polymorphic_identity": "email_user"}


class GoogleUser(User):
    __tablename__ = "google_users"

    user_id = Column(String(21), ForeignKey("users.user_id"), primary_key=True)
    verified = Column(Boolean, default=True)

    __mapper_args__ = {"polymorphic_identity": "google_user"}


class VerifyMailToken(User):
    __tablename__ = "verify_mail_token"

    user_id = Column(String(21), ForeignKey("users.user_id"), primary_key=True)
    verification_token = Column(String, nullable=True)
    token_expiration = Column(DateTime, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "verify_user_token"}


class OAuthState(Base):
    __tablename__ = "oauth_states"

    state = Column(String, primary_key=True, index=True)
    device_identifier = Column(String, nullable=False)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_current_time())
    expires_at = Column(DateTime, nullable=False)

    # Optional: Store user info if needed
    user_info = Column(String, nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    # Ensure that session_id is the primary key
    session_id = Column(String, primary_key=True, index=True)

    # Foreign key to the User table
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)

    # Device identifier for tracking sessions per device
    device_identifier = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Enforce that each user can only have one session per device
    __table_args__ = (
        UniqueConstraint("user_id", "device_identifier", name="user_device_uc"),
    )

    # Define the back reference to the User
    user = relationship("User", back_populates="sessions")


class SittingSession(Base):
    __tablename__ = "sitting_sessions"

    sitting_session_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )  # UUID as the primary key
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    blink = Column(JSON)
    sitting = Column(JSON)
    distance = Column(JSON)
    thoracic = Column(JSON)
    file_name = Column(String)
    thumbnail = Column(String)
    duration = Column(Integer)
    date = Column(DateTime, nullable=False, default=datetime.now)
    session_type = Column(String(50))
    is_complete = Column(Boolean, nullable=False)
