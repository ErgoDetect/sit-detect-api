from typing import Any, Dict, List
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    user_id: str
    email: EmailStr


class VideoNameRequest(BaseModel):
    video_name: str
    thumbnail: str


class VideoUploadRequest(BaseModel):
    video_name: str
    thumbnail: str
    files: List[Dict[str, Any]]
