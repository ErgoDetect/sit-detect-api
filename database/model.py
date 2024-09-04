from sqlalchemy import Column,Integer,String,ForeignKey
from sqlalchemy.orm import relationship
from database.config import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer,primary_key=True)
    email = Column(String(50),unique=True)
    password = Column(String(50))
    first_name = Column(String(50))
    last_name = Column(String(50))
    display_name = Column(String(50))
    picture = Column(String(100))
    sign_up_method = Column(String(50))
    
    tokens = relationship("OAuthToken", back_populates="user")
    
class OAuthToken(Base):
    __tablename__ = 'oauth_tokens'
    
    id = Column(Integer, primary_key=True, index=True)  # Primary key
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True, nullable=False)
    refresh_token = Column(String(100), unique=True, index=True)
    expires_in = Column(Integer)

    user = relationship("User", back_populates="tokens")

    
class Event(Base): 
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(50))  # Add necessary fields
    event_time = Column(String(50))  # Example of potential fields

class Video(Base): 
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True, index=True)
    video_url = Column(String(200))  # Example of a field to store the video URL
    uploaded_at = Column(String(50))  # Example of potential fields