from pydantic import BaseModel, EmailStr
from typing import Optional

class EmailBase(BaseModel):
    email: EmailStr
    display_name: Optional[str]

class EmailCreate(EmailBase):
    password: str