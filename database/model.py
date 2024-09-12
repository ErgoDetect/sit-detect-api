import datetime
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey,Boolean
from sqlalchemy.orm import relationship
from database.database import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(String(21), primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(128), nullable=True)
    display_name = Column(String(100), nullable=False)
    sign_up_method = Column(String(50), nullable=True)
    verified = Column(Boolean, default=False)
    
    session = relationship("UserSession", back_populates="user")


class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    user_id = Column(String(21), ForeignKey('users.user_id'), primary_key=True)
    session_id = Column(String(100), unique=True, nullable=False)  
    created_at = Column(DateTime, default=datetime.datetime.utcnow)  
    expires_at = Column(DateTime, nullable=False)  
    
    user = relationship("User", back_populates="session")