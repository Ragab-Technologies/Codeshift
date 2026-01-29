"""
Stress test for FastAPI 0.x + Pydantic v1 migration.

This file contains a complex FastAPI application using patterns from FastAPI 0.95
and Pydantic v1 that need to be migrated to FastAPI 0.100+ and Pydantic v2.

Migration patterns tested:
- Starlette imports -> FastAPI imports (responses, requests, websockets, background)
- Field/Query/Path/Body/Header/Cookie regex -> pattern
- Depends(use_cache=...) -> Depends(use_cached=...)
- FastAPI(openapi_prefix=...) -> FastAPI(root_path=...)
- Pydantic v1 Config class -> ConfigDict
- Pydantic validators -> field_validators/model_validators
- Pydantic method calls: .dict() -> .model_dump(), etc.
"""

from collections.abc import Generator
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, root_validator, validator
from starlette.background import BackgroundTasks

# ============================================================================
# IMPORTS REQUIRING MIGRATION (Starlette -> FastAPI)
# ============================================================================
from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from starlette.websockets import WebSocket, WebSocketDisconnect

# ============================================================================
# PYDANTIC V1 MODELS (require migration to v2)
# ============================================================================


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class Address(BaseModel):
    """Nested address model with regex validation."""

    street: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., regex=r"^[A-Z]{2}$")  # Needs migration to pattern=
    zip_code: str = Field(..., regex=r"^\d{5}(-\d{4})?$")  # Needs migration
    country: str = Field(default="US", regex=r"^[A-Z]{2}$")  # Needs migration

    class Config:
        """Pydantic v1 config - needs migration to model_config."""

        orm_mode = True
        validate_assignment = True


class ContactInfo(BaseModel):
    """Contact information with multiple regex patterns."""

    email: str = Field(..., regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")  # Needs migration
    phone: str | None = Field(None, regex=r"^\+?1?\d{10,14}$")  # Needs migration
    fax: str | None = Field(None, regex=r"^\+?1?\d{10,14}$")  # Needs migration

    class Config:
        """Pydantic v1 config."""

        extra = "forbid"


class UserPreferences(BaseModel):
    """User preferences with nested validation."""

    theme: str = Field(default="light", regex=r"^(light|dark|system)$")  # Needs migration
    language: str = Field(default="en", regex=r"^[a-z]{2}(-[A-Z]{2})?$")  # Needs migration
    timezone: str = Field(default="UTC")
    notifications_enabled: bool = True
    email_frequency: str = Field(default="daily", regex=r"^(instant|daily|weekly|never)$")


class UserBase(BaseModel):
    """Base user model with validators."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        regex=r"^[a-zA-Z][a-zA-Z0-9_-]*$",  # Needs migration
    )
    email: str = Field(..., regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")  # Needs migration
    full_name: str | None = Field(None, max_length=100)
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_verified: bool = False
    tags: list[str] = Field(default_factory=list, min_items=0, max_items=10)  # Needs migration

    @validator("username")
    def username_alphanumeric(cls, v):
        """Validate username is alphanumeric."""
        if not v[0].isalpha():
            raise ValueError("Username must start with a letter")
        return v

    @validator("email")
    def email_lowercase(cls, v):
        """Convert email to lowercase."""
        return v.lower()

    @validator("tags", each_item=True)
    def validate_tag(cls, v):
        """Validate each tag."""
        if len(v) > 50:
            raise ValueError("Tag too long")
        return v.strip().lower()


class UserCreate(UserBase):
    """User creation model with password validation."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        regex=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+$",
    )
    password_confirm: str
    address: Address | None = None
    contact: ContactInfo | None = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    @validator("password_confirm")
    def passwords_match(cls, v, values):
        """Validate passwords match."""
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")
        return v

    @root_validator(pre=True)
    def check_required_fields(cls, values):
        """Pre-validation root validator."""
        if not values.get("email") and not values.get("username"):
            raise ValueError("Either email or username must be provided")
        return values

    @root_validator
    def final_validation(cls, values):
        """Post-validation root validator."""
        if values.get("role") == UserRole.ADMIN and not values.get("is_verified"):
            raise ValueError("Admin users must be verified")
        return values

    class Config:
        """Pydantic v1 config - needs full migration."""

        orm_mode = True
        validate_assignment = True
        extra = "forbid"
        allow_mutation = True
        use_enum_values = True


class UserUpdate(BaseModel):
    """User update model with optional fields."""

    username: str | None = Field(None, min_length=3, max_length=50)
    email: str | None = Field(None, regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    full_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    role: UserRole | None = None
    address: Address | None = None
    preferences: UserPreferences | None = None

    class Config:
        """Pydantic v1 config."""

        orm_mode = True


class UserInDB(UserBase):
    """User model as stored in database."""

    id: UUID
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None
    address: Address | None = None
    contact: ContactInfo | None = None
    preferences: UserPreferences

    class Config:
        """Pydantic v1 config."""

        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class UserResponse(BaseModel):
    """Public user response model."""

    id: UUID
    username: str
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        """Pydantic v1 config."""

        orm_mode = True


# ============================================================================
# TOKEN AND AUTH MODELS
# ============================================================================


class Token(BaseModel):
    """JWT Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT Token payload."""

    sub: str
    exp: datetime
    iat: datetime
    jti: str
    role: UserRole
    scopes: list[str] = Field(default_factory=list)

    @validator("exp")
    def exp_must_be_future(cls, v):
        """Validate expiration is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("Token already expired")
        return v


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str = Field(..., min_length=10)


# ============================================================================
# ITEM/PRODUCT MODELS
# ============================================================================


class Category(BaseModel):
    """Product category."""

    id: int
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")  # Needs migration
    parent_id: int | None = None

    class Config:
        """Pydantic v1 config."""

        orm_mode = True


class ProductBase(BaseModel):
    """Base product model."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    sku: str = Field(..., regex=r"^[A-Z]{2,4}-\d{4,8}$")  # Needs migration
    price: float = Field(..., gt=0, le=1000000)
    discount_percent: float = Field(default=0, ge=0, le=100)
    quantity: int = Field(default=0, ge=0)
    category_ids: list[int] = Field(default_factory=list, min_items=1, max_items=5)
    tags: set[str] = Field(default_factory=set)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("tags", each_item=True, pre=True)
    def validate_product_tag(cls, v):
        """Validate product tags."""
        if isinstance(v, str):
            v = v.strip().lower()
            if len(v) > 30:
                raise ValueError("Tag too long")
        return v

    @root_validator
    def calculate_final_price(cls, values):
        """Calculate and store final price."""
        price = values.get("price", 0)
        discount = values.get("discount_percent", 0)
        values["final_price"] = price * (1 - discount / 100)
        return values

    class Config:
        """Pydantic v1 config."""

        orm_mode = True
        validate_assignment = True


class ProductCreate(ProductBase):
    """Product creation model."""

    images: list[str] = Field(default_factory=list, max_items=10)

    @validator("images", each_item=True)
    def validate_image_url(cls, v):
        """Validate image URLs."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Invalid image URL")
        return v


class ProductUpdate(BaseModel):
    """Product update model."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    price: float | None = Field(None, gt=0, le=1000000)
    discount_percent: float | None = Field(None, ge=0, le=100)
    quantity: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductResponse(ProductBase):
    """Product response model."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    final_price: float

    class Config:
        """Pydantic v1 config."""

        orm_mode = True


# ============================================================================
# ORDER MODELS
# ============================================================================


class OrderStatus(str, Enum):
    """Order status enumeration."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderItem(BaseModel):
    """Order item model."""

    product_id: int
    quantity: int = Field(..., gt=0, le=100)
    unit_price: float = Field(..., gt=0)
    discount: float = Field(default=0, ge=0)

    @property
    def total(self) -> float:
        """Calculate item total."""
        return (self.unit_price * self.quantity) - self.discount


class OrderCreate(BaseModel):
    """Order creation model."""

    items: list[OrderItem] = Field(..., min_items=1, max_items=50)
    shipping_address: Address
    billing_address: Address | None = None
    notes: str | None = Field(None, max_length=500)
    coupon_code: str | None = Field(None, regex=r"^[A-Z0-9]{4,12}$")  # Needs migration

    @root_validator
    def set_billing_address(cls, values):
        """Default billing address to shipping address."""
        if not values.get("billing_address"):
            values["billing_address"] = values.get("shipping_address")
        return values


class OrderResponse(BaseModel):
    """Order response model."""

    id: UUID
    user_id: UUID
    status: OrderStatus
    items: list[OrderItem]
    subtotal: float
    tax: float
    shipping_cost: float
    total: float
    shipping_address: Address
    billing_address: Address
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic v1 config."""

        orm_mode = True


# ============================================================================
# PAGINATION AND FILTER MODELS
# ============================================================================


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = None
    sort_order: str = Field(default="asc", regex=r"^(asc|desc)$")  # Needs migration


class ProductFilter(BaseModel):
    """Product filter parameters."""

    name_contains: str | None = None
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)
    category_ids: list[int] | None = None
    in_stock_only: bool = False
    tags: list[str] | None = None


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    page: int
    per_page: int
    total_pages: int

    @validator("total_pages", always=True)
    def calculate_total_pages(cls, v, values):
        """Calculate total pages."""
        total = values.get("total", 0)
        per_page = values.get("per_page", 20)
        return (total + per_page - 1) // per_page if per_page > 0 else 0


# ============================================================================
# WEBSOCKET MODELS
# ============================================================================


class WebSocketMessage(BaseModel):
    """WebSocket message model."""

    type: str = Field(..., regex=r"^[a-z_]+$")  # Needs migration
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sender_id: str | None = None

    class Config:
        """Pydantic v1 config."""

        extra = "allow"


class ChatMessage(BaseModel):
    """Chat message model."""

    room_id: str = Field(..., regex=r"^[a-zA-Z0-9_-]+$")  # Needs migration
    content: str = Field(..., min_length=1, max_length=2000)
    attachments: list[str] = Field(default_factory=list, max_items=5)


# ============================================================================
# FILE UPLOAD MODELS
# ============================================================================


class FileMetadata(BaseModel):
    """File metadata model."""

    filename: str = Field(..., regex=r"^[\w\-. ]+\.[a-zA-Z0-9]+$")  # Needs migration
    content_type: str
    size: int = Field(..., gt=0, le=10485760)  # 10MB max
    checksum: str = Field(..., regex=r"^[a-f0-9]{64}$")  # SHA-256, needs migration

    class Config:
        """Pydantic v1 config."""

        orm_mode = True


class FileUploadResponse(BaseModel):
    """File upload response."""

    id: UUID
    url: str
    metadata: FileMetadata
    created_at: datetime


# ============================================================================
# ERROR MODELS
# ============================================================================


class ErrorDetail(BaseModel):
    """Error detail model."""

    loc: list[str]
    msg: str
    type: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str = Field(..., regex=r"^[A-Z_]+$")  # Needs migration
    errors: list[ErrorDetail] | None = None
    request_id: str | None = None


# ============================================================================
# APPLICATION SETUP WITH OLD PATTERNS
# ============================================================================

# FastAPI app with deprecated openapi_prefix parameter
app = FastAPI(
    title="Stress Test API",
    description="Complex API for migration testing",
    version="1.0.0",
    openapi_prefix="/api/v1",  # Needs migration to root_path
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Routers
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["Users"])
products_router = APIRouter(prefix="/products", tags=["Products"])
orders_router = APIRouter(prefix="/orders", tags=["Orders"])
files_router = APIRouter(prefix="/files", tags=["Files"])
ws_router = APIRouter(prefix="/ws", tags=["WebSocket"])


# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================


async def get_db() -> Generator:
    """Database session dependency with yield."""
    db = {"connection": "fake_db_connection"}
    try:
        yield db
    finally:
        # Cleanup
        pass


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration to use_cached
) -> UserInDB:
    """Get current user from token."""
    # Fake implementation
    from uuid import uuid4

    return UserInDB(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        preferences=UserPreferences(),
    )


async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user, use_cache=True),  # Needs migration
) -> UserInDB:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


async def get_admin_user(
    current_user: UserInDB = Depends(get_current_active_user, use_cache=True),  # Needs migration
) -> UserInDB:
    """Get admin user only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str | None = Query(None, regex=r"^[a-z_]+$"),  # Needs migration
    sort_order: str = Query("asc", regex=r"^(asc|desc)$"),  # Needs migration
) -> PaginationParams:
    """Get pagination parameters."""
    return PaginationParams(
        page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order
    )


# ============================================================================
# CUSTOM MIDDLEWARE
# ============================================================================


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all responses."""
    import uuid

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    import time

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            code="HTTP_ERROR",
            request_id=getattr(request.state, "request_id", None),
        ).dict(),  # Needs migration to .model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Internal server error",
            code="INTERNAL_ERROR",
            request_id=getattr(request.state, "request_id", None),
        ).dict(),  # Needs migration to .model_dump()
    )


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: dict = Depends(get_db, use_cache=False),  # Needs migration
):
    """OAuth2 compatible token login."""
    # Fake implementation
    return Token(
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        expires_in=3600,
    )


@auth_router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """Refresh access token."""
    return Token(
        access_token="new_fake_access_token",
        refresh_token="new_fake_refresh_token",
        expires_in=3600,
    )


@auth_router.post("/register", response_model=UserResponse, status_code=HTTP_201_CREATED)
async def register_user(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: dict = Depends(get_db),
):
    """Register a new user."""
    # Send welcome email in background
    background_tasks.add_task(send_welcome_email, user.email)

    # Fake response using Pydantic v1 patterns
    user_data = user.dict(exclude={"password", "password_confirm"})  # Needs migration
    from uuid import uuid4

    return UserResponse(
        id=uuid4(),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=True,
        is_verified=False,
        created_at=datetime.utcnow(),
    )


@auth_router.post("/logout")
async def logout(
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Logout current user."""
    return {"message": "Successfully logged out"}


# ============================================================================
# USER ENDPOINTS
# ============================================================================


@users_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Get current user information."""
    return current_user


@users_router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """Update current user."""
    # Merge updates
    update_data = user_update.dict(exclude_unset=True)  # Needs migration
    for field, value in update_data.items():
        setattr(current_user, field, value)
    return current_user


@users_router.delete("/me", status_code=HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: UserInDB = Depends(get_current_active_user),
    db: dict = Depends(get_db),
):
    """Delete current user account."""
    return None


@users_router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_user_by_id(
    user_id: UUID = Path(..., description="User UUID"),
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """Get user by ID (admin only)."""
    # Fake implementation
    return UserResponse(
        id=user_id,
        username="someuser",
        email="user@example.com",
        full_name="Some User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
    )


@users_router.get("/", response_model=PaginatedResponse)
async def list_users(
    pagination: PaginationParams = Depends(get_pagination),
    role: UserRole | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=100),
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """List all users with pagination (admin only)."""
    # Fake implementation
    return PaginatedResponse(
        items=[],
        total=0,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=0,
    )


@users_router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID = Path(..., description="User UUID"),
    role: UserRole = Query(..., description="New role"),
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db),
):
    """Update user role (admin only)."""
    return UserResponse(
        id=user_id,
        username="someuser",
        email="user@example.com",
        full_name="Some User",
        role=role,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
    )


# ============================================================================
# PRODUCT ENDPOINTS
# ============================================================================


@products_router.get("/", response_model=PaginatedResponse)
async def list_products(
    pagination: PaginationParams = Depends(get_pagination),
    name: str | None = Query(None, max_length=100),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    category_id: int | None = Query(None),
    sku_pattern: str | None = Query(None, regex=r"^[A-Z]{2,4}-\d*$"),  # Needs migration
    in_stock: bool = Query(False),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """List products with filters."""
    return PaginatedResponse(
        items=[],
        total=0,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=0,
    )


@products_router.post("/", response_model=ProductResponse, status_code=HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db),
):
    """Create a new product (admin only)."""
    background_tasks.add_task(index_product_for_search, product.name)

    # Use Pydantic v1 patterns
    product_dict = product.dict()  # Needs migration to .model_dump()
    return ProductResponse(
        id=1,
        **product_dict,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        final_price=product.price * (1 - product.discount_percent / 100),
    )


@products_router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int = Path(..., ge=1, description="Product ID"),
    include_inactive: bool = Query(False),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """Get product by ID."""
    return ProductResponse(
        id=product_id,
        name="Test Product",
        sku="ABC-12345",
        price=99.99,
        discount_percent=10,
        quantity=100,
        category_ids=[1, 2],
        tags=set(),
        metadata={},
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        final_price=89.99,
    )


@products_router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product: ProductUpdate,
    product_id: int = Path(..., ge=1),
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db),
):
    """Update product (admin only)."""
    # Use Pydantic v1 patterns
    update_data = product.dict(exclude_unset=True)  # Needs migration
    return ProductResponse(
        id=product_id,
        name=update_data.get("name", "Test Product"),
        sku="ABC-12345",
        price=update_data.get("price", 99.99),
        discount_percent=update_data.get("discount_percent", 0),
        quantity=update_data.get("quantity", 100),
        category_ids=[1],
        tags=set(),
        metadata={},
        is_active=update_data.get("is_active", True),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        final_price=89.99,
    )


@products_router.delete("/{product_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int = Path(..., ge=1),
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db),
):
    """Delete product (admin only)."""
    return None


@products_router.get("/{product_id}/schema")
async def get_product_schema():
    """Get product JSON schema."""
    # Pydantic v1 pattern
    return ProductResponse.schema()  # Needs migration to .model_json_schema()


# ============================================================================
# ORDER ENDPOINTS
# ============================================================================


@orders_router.post("/", response_model=OrderResponse, status_code=HTTP_201_CREATED)
async def create_order(
    order: OrderCreate,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_active_user),
    db: dict = Depends(get_db),
):
    """Create a new order."""
    background_tasks.add_task(send_order_confirmation, current_user.email)
    background_tasks.add_task(update_inventory, order.items)

    from uuid import uuid4

    return OrderResponse(
        id=uuid4(),
        user_id=current_user.id,
        status=OrderStatus.PENDING,
        items=order.items,
        subtotal=sum(item.unit_price * item.quantity for item in order.items),
        tax=10.0,
        shipping_cost=5.0,
        total=100.0,
        shipping_address=order.shipping_address,
        billing_address=order.billing_address or order.shipping_address,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@orders_router.get("/", response_model=PaginatedResponse)
async def list_orders(
    pagination: PaginationParams = Depends(get_pagination),
    status: OrderStatus | None = Query(None),
    current_user: UserInDB = Depends(get_current_active_user),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """List user's orders."""
    return PaginatedResponse(
        items=[],
        total=0,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=0,
    )


@orders_router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID = Path(..., description="Order UUID"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: dict = Depends(get_db, use_cache=True),  # Needs migration
):
    """Get order by ID."""
    return OrderResponse(
        id=order_id,
        user_id=current_user.id,
        status=OrderStatus.PENDING,
        items=[],
        subtotal=0,
        tax=0,
        shipping_cost=0,
        total=0,
        shipping_address=Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            zip_code="12345",
        ),
        billing_address=Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            zip_code="12345",
        ),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@orders_router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID = Path(...),
    status: OrderStatus = Query(...),
    current_user: UserInDB = Depends(get_admin_user),
    db: dict = Depends(get_db),
):
    """Update order status (admin only)."""
    from uuid import uuid4

    return OrderResponse(
        id=order_id,
        user_id=uuid4(),
        status=status,
        items=[],
        subtotal=0,
        tax=0,
        shipping_cost=0,
        total=0,
        shipping_address=Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            zip_code="12345",
        ),
        billing_address=Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            zip_code="12345",
        ),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@orders_router.delete("/{order_id}", status_code=HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: UUID = Path(...),
    current_user: UserInDB = Depends(get_current_active_user),
    db: dict = Depends(get_db),
):
    """Cancel an order."""
    return None


# ============================================================================
# FILE UPLOAD ENDPOINTS
# ============================================================================


@files_router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    description: str | None = Form(None, max_length=500),
    tags: list[str] = Form(default=[]),
    current_user: UserInDB = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = Depends(),
):
    """Upload a file."""
    import hashlib
    from uuid import uuid4

    # Calculate checksum
    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()

    background_tasks.add_task(process_uploaded_file, file.filename)

    return FileUploadResponse(
        id=uuid4(),
        url=f"/files/{uuid4()}/{file.filename}",
        metadata=FileMetadata(
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size=len(content),
            checksum=checksum,
        ),
        created_at=datetime.utcnow(),
    )


@files_router.post("/upload/multiple", response_model=list[FileUploadResponse])
async def upload_multiple_files(
    files: list[UploadFile] = File(...),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Upload multiple files."""
    responses = []
    for file in files:
        import hashlib
        from uuid import uuid4

        content = await file.read()
        checksum = hashlib.sha256(content).hexdigest()

        responses.append(
            FileUploadResponse(
                id=uuid4(),
                url=f"/files/{uuid4()}/{file.filename}",
                metadata=FileMetadata(
                    filename=file.filename,
                    content_type=file.content_type or "application/octet-stream",
                    size=len(content),
                    checksum=checksum,
                ),
                created_at=datetime.utcnow(),
            )
        )
    return responses


@files_router.get("/download/{file_id}")
async def download_file(
    file_id: UUID = Path(...),
    current_user: UserInDB = Depends(get_current_active_user),
) -> FileResponse:
    """Download a file."""
    # Fake implementation
    return FileResponse(
        path="/tmp/fake_file.txt",
        filename="downloaded_file.txt",
        media_type="application/octet-stream",
    )


@files_router.get("/stream/{file_id}")
async def stream_file(
    file_id: UUID = Path(...),
    current_user: UserInDB = Depends(get_current_active_user),
) -> StreamingResponse:
    """Stream a file."""

    async def file_iterator():
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"

    return StreamingResponse(
        file_iterator(),
        media_type="application/octet-stream",
    )


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================


class ConnectionManager:
    """WebSocket connection manager."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        """Connect to a room."""
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        """Disconnect from a room."""
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)

    async def broadcast(self, message: str, room_id: str):
        """Broadcast message to room."""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)


manager = ConnectionManager()


@ws_router.websocket("/chat/{room_id}")
async def websocket_chat(
    websocket: WebSocket,
    room_id: str = Path(..., regex=r"^[a-zA-Z0-9_-]+$"),  # Needs migration
    token: str | None = Query(None),
):
    """WebSocket chat endpoint."""
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Parse and validate message
            try:
                message = ChatMessage.parse_raw(data)  # Pydantic v1 - needs migration
                # Broadcast message
                broadcast_data = WebSocketMessage(
                    type="chat_message",
                    payload=message.dict(),  # Needs migration
                    sender_id=token,
                )
                await manager.broadcast(broadcast_data.json(), room_id)  # Needs migration
            except Exception as e:
                error_msg = WebSocketMessage(
                    type="error",
                    payload={"message": str(e)},
                )
                await websocket.send_text(error_msg.json())  # Needs migration
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        disconnect_msg = WebSocketMessage(
            type="user_left",
            payload={"room_id": room_id},
        )
        await manager.broadcast(disconnect_msg.json(), room_id)  # Needs migration


@ws_router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., regex=r"^[a-zA-Z0-9_-]+$"),  # Needs migration
):
    """WebSocket notifications endpoint."""
    await websocket.accept()
    try:
        while True:
            # Send periodic notifications
            import asyncio

            await asyncio.sleep(30)
            notification = WebSocketMessage(
                type="ping",
                payload={"timestamp": datetime.utcnow().isoformat()},
            )
            await websocket.send_text(notification.json())  # Needs migration
    except WebSocketDisconnect:
        pass


# ============================================================================
# ADDITIONAL ENDPOINTS FOR COMPLETENESS
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint."""
    return """
    <html>
        <head><title>Stress Test API</title></head>
        <body><h1>Welcome to the Stress Test API</h1></body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/redirect")
async def redirect_example() -> RedirectResponse:
    """Redirect example."""
    return RedirectResponse(url="/")


@app.get("/headers")
async def header_example(
    user_agent: str = Header(...),
    accept_language: str = Header(None, regex=r"^[a-z]{2}(-[A-Z]{2})?$"),  # Needs migration
    x_request_id: str = Header(None, regex=r"^[a-f0-9-]+$"),  # Needs migration
    x_custom: str = Header(None, alias="X-Custom-Header"),
):
    """Header example with regex patterns."""
    return {
        "user_agent": user_agent,
        "accept_language": accept_language,
        "x_request_id": x_request_id,
        "x_custom": x_custom,
    }


@app.get("/cookies")
async def cookie_example(
    session_id: str = Cookie(None, regex=r"^[a-f0-9]{32}$"),  # Needs migration
    tracking_id: str = Cookie(None, regex=r"^[A-Z0-9]{10}$"),  # Needs migration
):
    """Cookie example with regex patterns."""
    return {
        "session_id": session_id,
        "tracking_id": tracking_id,
    }


@app.get("/schema/user")
async def get_user_schema():
    """Get user schema using Pydantic v1 pattern."""
    schema = UserCreate.schema()  # Needs migration to .model_json_schema()
    return JSONResponse(content=schema)


@app.get("/schema/product")
async def get_product_schema_json():
    """Get product schema as JSON."""
    return JSONResponse(
        content=ProductCreate.schema_json()  # Pydantic v1 - needs careful migration
    )


@app.get("/validate/user")
async def validate_user_data(
    data: str = Query(..., description="JSON user data"),
):
    """Validate user data using Pydantic v1 pattern."""
    import json

    user_data = json.loads(data)
    user = UserCreate.parse_obj(user_data)  # Needs migration to .model_validate()
    return user.dict()  # Needs migration to .model_dump()


@app.get("/fields/user")
async def get_user_fields():
    """Get user model fields using Pydantic v1 pattern."""
    fields = UserCreate.__fields__  # Needs migration to model_fields
    return {
        name: {
            "type": str(field.outer_type_),
            "required": field.required,
            "default": str(field.default) if field.default else None,
        }
        for name, field in fields.items()
    }


# ============================================================================
# BACKGROUND TASK FUNCTIONS
# ============================================================================


async def send_welcome_email(email: str) -> None:
    """Send welcome email."""
    pass


async def send_order_confirmation(email: str) -> None:
    """Send order confirmation email."""
    pass


async def update_inventory(items: list[OrderItem]) -> None:
    """Update inventory after order."""
    pass


async def index_product_for_search(name: str) -> None:
    """Index product for search."""
    pass


async def process_uploaded_file(filename: str) -> None:
    """Process uploaded file."""
    pass


# ============================================================================
# INCLUDE ROUTERS
# ============================================================================

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(files_router)
app.include_router(ws_router)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
