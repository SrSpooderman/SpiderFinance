from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.http.schemas import ORMModel


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


class AdminCreateUserIn(BaseModel):
    email: EmailStr


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    email: EmailStr


class AdminPasswordOut(BaseModel):
    user: UserOut
    password: str


class ProfilePhotoOut(BaseModel):
    data_url: str | None


class SettingsOut(ORMModel):
    currency: str
    locale: str
    timezone: str
    theme: Literal["light-teal", "light-red", "dark-red", "dark-purple"]


class SettingsPatch(BaseModel):
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    locale: str | None = Field(default=None, min_length=2, max_length=32)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    theme: Literal["light-teal", "light-red", "dark-red", "dark-purple"] | None = None


