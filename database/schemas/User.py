from pydantic import BaseModel, EmailStr

class User (BaseModel):
    user_id:str
    email: EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
