from typing import List
from pydantic import BaseModel, field_validator


class SessionSummary(BaseModel):
    session_id: str
    date: str
    file_name: str
    blink: List
    sitting: List
    distance: List
    thoracic: List
    duration: int

    # Validator to ensure lists are returned even if None
    @field_validator("blink", "sitting", "distance", "thoracic")
    def default_empty_list(cls, v):
        return v if v is not None else []


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
