"""Authentication router for the PyResolve API."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status

from pyresolve.api.auth import (
    CurrentUser,
    generate_api_key,
)
from pyresolve.api.database import get_database
from pyresolve.api.models.auth import (
    APIKey,
    APIKeyCreate,
    APIKeyResponse,
    DeviceCodeRequest,
    DeviceCodeResponse,
    DeviceTokenRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserInfo,
)

router = APIRouter()

# In-memory storage for device codes (in production, use Redis)
_device_codes: dict[str, dict] = {}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(user: CurrentUser) -> UserInfo:
    """Get current authenticated user information."""
    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    return UserInfo(
        id=profile["id"],
        email=profile["email"],
        full_name=profile.get("full_name"),
        tier=profile.get("tier", "free"),
        stripe_customer_id=profile.get("stripe_customer_id"),
        created_at=profile["created_at"],
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Login with email and password, returns an API key.

    This endpoint authenticates against Supabase Auth and creates
    a new API key for CLI usage.
    """
    from pyresolve.api.database import get_supabase_anon_client

    client = get_supabase_anon_client()

    try:
        # Authenticate with Supabase
        auth_response = client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from e

    if not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_id = auth_response.user.id

    # Get or create profile
    db = get_database()
    profile = db.get_profile_by_id(user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    # Generate a new API key
    full_key, key_prefix, key_hash = generate_api_key()

    # Store the API key
    db.create_api_key(
        user_id=user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="CLI Login Key",
    )

    return LoginResponse(
        api_key=full_key,
        user=UserInfo(
            id=profile["id"],
            email=profile["email"],
            full_name=profile.get("full_name"),
            tier=profile.get("tier", "free"),
            stripe_customer_id=profile.get("stripe_customer_id"),
            created_at=profile["created_at"],
        ),
    )


@router.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest) -> LoginResponse:
    """Register a new user account.

    Creates a new user in Supabase Auth and returns an API key for CLI usage.
    The profile is automatically created by a database trigger.
    """
    from pyresolve.api.database import get_supabase_anon_client

    client = get_supabase_anon_client()

    try:
        # Create user in Supabase Auth
        auth_response = client.auth.sign_up(
            {
                "email": request.email,
                "password": request.password,
                "options": {"data": {"full_name": request.full_name} if request.full_name else {}},
            }
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "already registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please try again.",
        ) from e

    if not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please try again.",
        )

    user_id = auth_response.user.id

    # Wait briefly for the trigger to create the profile
    import asyncio

    await asyncio.sleep(0.5)

    # Get the profile (created by database trigger)
    db = get_database()
    profile = db.get_profile_by_id(user_id)

    if not profile:
        # Profile wasn't created by trigger - create it manually
        try:
            db.client.table("profiles").insert(
                {
                    "id": user_id,
                    "email": request.email,
                    "full_name": request.full_name or "",
                    "tier": "free",
                }
            ).execute()
            profile = db.get_profile_by_id(user_id)
        except Exception:
            pass

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account created but profile setup failed. Please try logging in.",
        )

    # Generate a new API key
    full_key, key_prefix, key_hash = generate_api_key()

    # Store the API key
    db.create_api_key(
        user_id=user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="CLI Registration Key",
    )

    return LoginResponse(
        api_key=full_key,
        user=UserInfo(
            id=profile["id"],
            email=profile["email"],
            full_name=profile.get("full_name"),
            tier=profile.get("tier", "free"),
            stripe_customer_id=profile.get("stripe_customer_id"),
            created_at=profile["created_at"],
        ),
        message="Registration successful",
    )


@router.post("/device/code", response_model=DeviceCodeResponse)
async def request_device_code(request: DeviceCodeRequest) -> DeviceCodeResponse:
    """Request a device code for CLI authentication.

    This initiates the device code flow for CLI authentication.
    The user will receive a code to enter in their browser.
    """
    # Generate codes
    device_code = secrets.token_urlsafe(32)
    user_code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
    user_code = f"{user_code[:4]}-{user_code[4:]}"  # Format: XXXX-XXXX

    # Store for later verification
    _device_codes[device_code] = {
        "user_code": user_code,
        "client_id": request.client_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
        "user_id": None,  # Will be set when user authenticates
        "status": "pending",
    }

    return DeviceCodeResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri="https://pyresolve.dev/device",
        expires_in=900,
        interval=5,
    )


@router.post("/device/token", response_model=LoginResponse)
async def exchange_device_code(request: DeviceTokenRequest) -> LoginResponse:
    """Exchange a device code for an API key.

    The CLI polls this endpoint until the user completes authentication.
    """
    device_data = _device_codes.get(request.device_code)

    if not device_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device code",
        )

    # Check expiration
    if datetime.now(timezone.utc) > device_data["expires_at"]:
        del _device_codes[request.device_code]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device code expired",
        )

    # Check status
    if device_data["status"] == "pending":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="authorization_pending",
        )

    if device_data["status"] == "denied":
        del _device_codes[request.device_code]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User denied the request",
        )

    if device_data["status"] != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device code status",
        )

    # Get user info
    user_id = device_data["user_id"]
    db = get_database()
    profile = db.get_profile_by_id(user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    # Generate API key
    full_key, key_prefix, key_hash = generate_api_key()

    db.create_api_key(
        user_id=user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="CLI Device Key",
    )

    # Clean up device code
    del _device_codes[request.device_code]

    return LoginResponse(
        api_key=full_key,
        user=UserInfo(
            id=profile["id"],
            email=profile["email"],
            full_name=profile.get("full_name"),
            tier=profile.get("tier", "free"),
            stripe_customer_id=profile.get("stripe_customer_id"),
            created_at=profile["created_at"],
        ),
    )


@router.post("/device/approve")
async def approve_device_code(user_code: str, user: CurrentUser) -> dict:
    """Approve a device code (called from web UI after user logs in)."""
    # Find the device code by user code
    for device_code, data in _device_codes.items():
        if data["user_code"] == user_code.upper().replace("-", "").strip():
            if datetime.now(timezone.utc) > data["expires_at"]:
                del _device_codes[device_code]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Device code expired",
                )

            data["user_id"] = user.user_id
            data["status"] = "approved"
            return {"message": "Device approved successfully"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Invalid user code",
    )


@router.get("/keys", response_model=list[APIKey])
async def list_api_keys(user: CurrentUser) -> list[APIKey]:
    """List all API keys for the current user."""
    db = get_database()

    result = (
        db.client.table("api_keys")
        .select("*")
        .eq("user_id", user.user_id)
        .eq("revoked", False)
        .order("created_at", desc=True)
        .execute()
    )

    return [
        APIKey(
            id=key["id"],
            name=key["name"],
            key_prefix=key["key_prefix"],
            scopes=key.get("scopes", []),
            revoked=key["revoked"],
            last_used_at=key.get("last_used_at"),
            expires_at=key.get("expires_at"),
            created_at=key["created_at"],
        )
        for key in result.data
    ]


@router.post("/keys", response_model=APIKeyResponse)
async def create_api_key(request: APIKeyCreate, user: CurrentUser) -> APIKeyResponse:
    """Create a new API key."""
    db = get_database()

    # Generate the key
    full_key, key_prefix, key_hash = generate_api_key()

    # Store it
    result = db.create_api_key(
        user_id=user.user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=request.name,
        scopes=request.scopes,
    )

    return APIKeyResponse(
        id=result["id"],
        name=request.name,
        key=full_key,  # Only time the full key is returned
        key_prefix=key_prefix,
        scopes=request.scopes,
        created_at=result["created_at"],
    )


@router.delete("/keys/{key_id}")
async def revoke_api_key(key_id: str, user: CurrentUser) -> dict:
    """Revoke an API key."""
    db = get_database()

    # Verify ownership
    result = db.client.table("api_keys").select("user_id").eq("id", key_id).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if result.data[0]["user_id"] != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this key",
        )

    # Revoke
    success = db.revoke_api_key(key_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke key",
        )

    return {"message": "API key revoked successfully"}


@router.post("/logout")
async def logout(user: CurrentUser) -> dict:
    """Logout by revoking the current API key."""
    if user.api_key_id:
        db = get_database()
        db.revoke_api_key(user.api_key_id)

    return {"message": "Logged out successfully"}
