from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    password: str = Field(min_length=8, max_length=72)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    role: str
    department: str
    avatar_url: Optional[str] = None
    created_at: datetime

    # Preferensi personal per-user
    language: Optional[str] = "English"
    appearance: Optional[str] = "light"
    notify_report_success: Optional[bool] = True
    notify_report_failed: Optional[bool] = True
    password_set: Optional[bool] = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None