from pydantic import BaseModel, EmailStr


class User(BaseModel):
    user_id: str
    email: EmailStr


class VideoNameRequest(BaseModel):
    video_name: str
