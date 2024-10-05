from sqlalchemy import Column, DateTime, String, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from auth.token import get_current_time
from database.database import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(String(21), primary_key=True, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(128), nullable=True)
    display_name = Column(String(100), nullable=False)
    sign_up_method = Column(String(50), nullable=True)
    verified = Column(Boolean, default=False)
    
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = 'user_sessions'

    # Ensure that session_id is the primary key
    session_id = Column(String, primary_key=True, index=True)
    
    # Foreign key to the User table
    user_id = Column(String, ForeignKey('users.user_id'), nullable=False)
    
    # Device identifier for tracking sessions per device
    device_identifier = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Optional: Enforce that each user can only have one session per device
    __table_args__ = (UniqueConstraint('user_id', 'device_identifier', name='user_device_uc'),)

    user = relationship("User", back_populates="sessions")
