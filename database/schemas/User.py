from typing import List
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    user_id: str
    email: EmailStr


class VideoNameRequest(BaseModel):
    video_name: str
    thumbnail: str


class SittingSessionResponse(BaseModel):
    sitting_session_id: str
    blink: List  # List to specify that it is a list of items, you can use a more specific type if you know it
    sitting: List
    distance: List
    thoracic: List
    file_name: List
    date: str

    class Config:
        orm_mode = True
