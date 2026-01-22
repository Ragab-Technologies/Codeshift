"""Authentication models for the PyResolve API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserInfo(BaseModel):
    """User profile information."""

    id: str
    email: EmailStr
    full_name: Optional[str] = None
    tier: str = "free"
    stripe_customer_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(default="CLI Key", min_length=1, max_length=100)
    scopes: list[str] = Field(default=["read", "write"])


class APIKey(BaseModel):
    """API key information (without the secret)."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    revoked: bool = False
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    """Response when creating a new API key (includes full key once)."""

    id: str
    name: str
    key: str  # Full API key - only shown once
    key_prefix: str
    scopes: list[str]
    created_at: datetime


class TokenResponse(BaseModel):
    """Response for authentication token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class LoginRequest(BaseModel):
    """Request for CLI login."""

    email: EmailStr
    password: str = Field(min_length=6)


class LoginResponse(BaseModel):
    """Response for CLI login."""

    api_key: str
    user: UserInfo
    message: str = "Login successful"


class DeviceCodeRequest(BaseModel):
    """Request to initiate device code flow."""

    client_id: str = "pyresolve-cli"


class DeviceCodeResponse(BaseModel):
    """Response with device code for authentication."""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int = 900  # 15 minutes
    interval: int = 5  # Polling interval in seconds


class DeviceTokenRequest(BaseModel):
    """Request to exchange device code for token."""

    device_code: str
    client_id: str = "pyresolve-cli"
