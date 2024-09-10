from sqlalchemy import Column, Integer, String, ForeignKey,Boolean
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
    
    tokens = relationship("OAuthToken", back_populates="user")

class OAuthToken(Base):
    __tablename__ = 'oauth_tokens'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), ForeignKey('users.user_id'), nullable=False)
    refresh_token = Column(String(100), unique=True, index=True)
    expires_in = Column(Integer)

    user = relationship("User", back_populates="tokens")
