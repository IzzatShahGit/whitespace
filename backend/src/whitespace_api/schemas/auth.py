from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    # NIST guidance: length matters, composition rules don't.
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    email_verified: bool
    has_password: bool
    created_at: datetime
    is_admin: bool = Field(default=False, description="Can open the usage page")


class UpdateMeRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str | None = Field(
        default=None, max_length=128, description="Required when the account has a password"
    )
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str | None = Field(
        default=None, max_length=128, description="Required when the account has a password"
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class ProvidersOut(BaseModel):
    password: bool
    google: bool
    password_reset: bool = False
