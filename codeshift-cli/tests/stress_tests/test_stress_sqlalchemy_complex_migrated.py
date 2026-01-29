"""
Stress test for SQLAlchemy 1.4 -> 2.0 migration.

This module tests VERY complex SQLAlchemy 1.4 patterns that need to be migrated to 2.0:
- 8+ related models with ForeignKey, relationship, backref
- Complex query chains with joins, subqueries, CTEs
- session.query() patterns throughout
- engine.execute() raw SQL
- Hybrid properties and expressions
- Polymorphic inheritance (joined, single table)
- Association objects and many-to-many
- Custom column types
- Event listeners
- Composite primary keys
- Index and constraint definitions
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    TypeDecorator,
    UniqueConstraint,
    and_,
    case,
    create_engine,
    event,
    exists,
    func,
    literal_column,
    not_,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    aliased,
    column_property,
    contains_eager,
    deferred,
    joinedload,
    relationship,
    selectinload,
    sessionmaker,
    subqueryload,
    validates,
    with_polymorphic,
)
from sqlalchemy.sql import expression, func


class Base(DeclarativeBase):
    pass


# =============================================================================
# CUSTOM COLUMN TYPES
# =============================================================================
class MoneyType(TypeDecorator):
    """Custom type for storing money as integer cents."""
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Any) -> int | None:
        if value is not None:
            return int(value * 100)
        return None

    def process_result_value(self, value: int | None, dialect: Any) -> Decimal | None:
        if value is not None:
            return Decimal(value) / 100
        return None


class EncryptedString(TypeDecorator):
    """Custom type for encrypted storage."""
    impl = String(500)
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        if value:
            return f"encrypted:{value}"
        return None

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        if value and value.startswith("encrypted:"):
            return value[10:]
        return value


# =============================================================================
# ENUMS
# =============================================================================
class UserRole(enum.Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class OrderStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ContentType(enum.Enum):
    ARTICLE = "article"
    VIDEO = "video"
    PODCAST = "podcast"


# =============================================================================
# ASSOCIATION TABLES (Many-to-Many)
# =============================================================================
user_group_association = Table(
    "user_group_association",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.utcnow),
    Column("role", String(50), default="member"),
)

product_category_association = Table(
    "product_category_association",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True),
)

tag_content_association = Table(
    "tag_content_association",
    Base.metadata,
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("content_id", Integer, ForeignKey("content.id"), primary_key=True),
)


# =============================================================================
# MODEL 1: User with Hybrid Properties
# =============================================================================
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("length(username) >= 3", name="ck_users_username_length"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False)
    password_hash = Column(EncryptedString, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    login_count = Column(Integer, default=0)
    profile_data = Column(JSONB, default={})

    # Relationships with backref (1.4 style)
    addresses = relationship("Address", backref=backref("user", lazy="joined"))
    orders = relationship("Order", backref="user", lazy="dynamic")
    reviews = relationship("Review", backref="author", foreign_keys="Review.author_id")
    groups = relationship("Group", secondary=user_group_association, backref="members")

    # Self-referential relationship
    manager_id = Column(Integer, ForeignKey("users.id"))
    subordinates = relationship("User", backref=backref("manager", remote_side=[id]))

    # Deferred columns for expensive data
    bio = deferred(Column(Text))
    avatar_data = deferred(Column(String(10000)))

    @hybrid_property
    def full_name(self) -> str:
        """Hybrid property for full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.username

    @full_name.expression
    def full_name(cls) -> expression.ClauseElement:
        """SQL expression for full name."""
        return case(
            (
                and_(cls.first_name != None, cls.last_name != None),
                cls.first_name + " " + cls.last_name,
            ),
            else_=func.coalesce(cls.first_name, cls.last_name, cls.username),
        )

    @hybrid_method
    def has_role(self, role: UserRole) -> bool:
        """Check if user has a specific role."""
        return self.role == role

    @has_role.expression
    def has_role(cls, role: UserRole) -> expression.ClauseElement:
        """SQL expression for role check."""
        return cls.role == role

    @validates("email")
    def validate_email(self, key: str, email: str) -> str:
        if "@" not in email:
            raise ValueError("Invalid email format")
        return email.lower()


# =============================================================================
# MODEL 2: Address with Composite Key
# =============================================================================
class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (
        PrimaryKeyConstraint("id", "user_id", name="pk_addresses"),
        Index("ix_addresses_zip", "zip_code"),
    )

    id = Column(Integer, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address_type = Column(String(20), default="home")
    street_address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100))
    zip_code = Column(String(20))
    country = Column(String(100), default="USA")
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Column property for formatted address
    formatted_address = column_property(
        street_address + ", " + city + " " + func.coalesce(zip_code, "")
    )


# =============================================================================
# MODEL 3: Group for Many-to-Many
# =============================================================================
class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationship to creator
    created_by = relationship("User", foreign_keys=[created_by_id])


# =============================================================================
# MODEL 4-5: Polymorphic Inheritance - Content System
# =============================================================================
class Content(Base):
    """Base class for polymorphic content."""
    __tablename__ = "content"
    __mapper_args__ = {
        "polymorphic_identity": "content",
        "polymorphic_on": "type",
    }

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True)
    body = Column(Text)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    view_count = Column(Integer, default=0)

    author = relationship("User", backref="content_items")
    tags = relationship("Tag", secondary=tag_content_association, backref="content_items")


class Article(Content):
    """Article content - joined table inheritance."""
    __tablename__ = "articles"
    __mapper_args__ = {
        "polymorphic_identity": "article",
    }

    id = Column(Integer, ForeignKey("content.id"), primary_key=True)
    summary = Column(Text)
    word_count = Column(Integer)
    reading_time_minutes = Column(Integer)
    featured_image_url = Column(String(500))


class Video(Content):
    """Video content - joined table inheritance."""
    __tablename__ = "videos"
    __mapper_args__ = {
        "polymorphic_identity": "video",
    }

    id = Column(Integer, ForeignKey("content.id"), primary_key=True)
    video_url = Column(String(500), nullable=False)
    duration_seconds = Column(Integer)
    thumbnail_url = Column(String(500))
    transcript = Column(Text)


# =============================================================================
# MODEL 6: Tag
# =============================================================================
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    slug = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    color = Column(String(7))  # Hex color code


# =============================================================================
# MODEL 7: Category (Self-Referential Tree)
# =============================================================================
class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index("ix_categories_parent", "parent_id"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("categories.id"))
    level = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Self-referential relationships
    parent = relationship("Category", remote_side=[id], backref=backref("children", lazy="dynamic"))
    products = relationship("Product", secondary=product_category_association, backref="categories")


# =============================================================================
# MODEL 8: Product
# =============================================================================
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_sku", "sku"),
        Index("ix_products_price", "price"),
        CheckConstraint("price >= 0", name="ck_products_price_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_positive"),
    )

    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(MoneyType, nullable=False)
    sale_price = Column(MoneyType)
    cost = Column(MoneyType)
    stock_quantity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    weight = Column(Float)
    dimensions = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order_items = relationship("OrderItem", backref="product")
    reviews = relationship("Review", backref="product")

    @hybrid_property
    def is_on_sale(self) -> bool:
        return self.sale_price is not None and self.sale_price < self.price

    @is_on_sale.expression
    def is_on_sale(cls) -> expression.ClauseElement:
        return and_(cls.sale_price != None, cls.sale_price < cls.price)

    @hybrid_property
    def effective_price(self) -> Decimal:
        return self.sale_price if self.is_on_sale else self.price

    @effective_price.expression
    def effective_price(cls) -> expression.ClauseElement:
        return case((cls.is_on_sale, cls.sale_price), else_=cls.price)


# =============================================================================
# MODEL 9: Order with Status
# =============================================================================
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id", "user_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    order_number = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    shipping_address_id = Column(Integer)
    billing_address_id = Column(Integer)
    subtotal = Column(MoneyType, nullable=False, default=0)
    tax = Column(MoneyType, default=0)
    shipping = Column(MoneyType, default=0)
    discount = Column(MoneyType, default=0)
    total = Column(MoneyType, nullable=False, default=0)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    items = relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    @hybrid_property
    def item_count(self) -> int:
        return len(self.items)

    @item_count.expression
    def item_count(cls) -> expression.ClauseElement:
        from sqlalchemy import select
        return (
            select(func.count(OrderItem.id))
            .where(OrderItem.order_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )


# =============================================================================
# MODEL 10: OrderItem (Association Object Pattern)
# =============================================================================
class OrderItem(Base):
    """Association object for Order-Product relationship with extra data."""
    __tablename__ = "order_items"
    __table_args__ = (
        PrimaryKeyConstraint("order_id", "product_id"),
    )

    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(MoneyType, nullable=False)
    discount = Column(MoneyType, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    @hybrid_property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity) - (self.discount or 0)

    @line_total.expression
    def line_total(cls) -> expression.ClauseElement:
        return (cls.unit_price * cls.quantity) - func.coalesce(cls.discount, 0)


# =============================================================================
# MODEL 11: Review
# =============================================================================
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("author_id", "product_id", name="uq_reviews_author_product"),
        Index("ix_reviews_rating", "rating"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    title = Column(String(255))
    body = Column(Text)
    is_verified_purchase = Column(Boolean, default=False)
    helpful_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# EVENT LISTENERS
# =============================================================================
@event.listens_for(User, "before_insert")
def user_before_insert(mapper: Any, connection: Any, target: User) -> None:
    """Set default values before inserting user."""
    if not target.created_at:
        target.created_at = datetime.utcnow()


@event.listens_for(Order, "after_update")
def order_after_update(mapper: Any, connection: Any, target: Order) -> None:
    """Trigger actions after order update."""
    if target.status == OrderStatus.COMPLETED:
        target.completed_at = datetime.utcnow()


@event.listens_for(Session, "before_flush")
def session_before_flush(session: Session, flush_context: Any, instances: Any) -> None:
    """Update timestamps before flushing."""
    for obj in session.dirty:
        if hasattr(obj, "updated_at"):
            obj.updated_at = datetime.utcnow()


# =============================================================================
# DATABASE SETUP AND COMPLEX QUERIES
# =============================================================================
def setup_database() -> tuple[Any, Session]:
    """Create engine and session - SQLAlchemy 1.4 style."""
    engine = create_engine(
        "sqlite:///stress_test.db",
        echo=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    return engine, session


def complex_query_examples(session: Session) -> None:
    """Examples of complex SQLAlchemy 1.4 query patterns that need migration."""

    # ==========================================================================
    # BASIC session.query() patterns
    # ==========================================================================

    # Simple query with all()
    all_users = session.execute(select(User)).scalars().all()

    # Query with filter and first()
    admin_user = session.execute(select(User).where(User.role == UserRole.ADMIN)).scalars().first()

    # Query with filter_by
    active_users = session.execute(select(User).where(User.is_active == True)).scalars().all()

    # Query with get()
    user_by_id = session.get(User, 1)

    # Query with one()
    single_user = session.execute(select(User).where(User.id == 1)).scalars().one()

    # Query with one_or_none()
    maybe_user = session.execute(select(User).where(User.email == "test@example.com")).scalars().one_or_none()

    # Query with count()
    user_count = session.execute(select(func.count()).select_from(User)).scalar()
    active_user_count = session.execute(select(func.count()).select_from(User).where(User.is_active == True)).scalar()

    # ==========================================================================
    # CHAINED FILTERS
    # ==========================================================================

    # Multiple filters
    filtered_users = session.execute(select(User).where(User.is_active == True).where(User.is_verified == True).where(User.role == UserRole.USER)).scalars().all()

    # Filter with and_/or_
    complex_filter = session.execute(select(User).where(and_(
                User.is_active == True,
                or_(
                    User.role == UserRole.ADMIN,
                    User.role == UserRole.MODERATOR,
                ),
            ))).scalars().all()

    # ==========================================================================
    # JOINS
    # ==========================================================================

    # Simple join
    users_with_orders = session.execute(select(User).where(Order.status == OrderStatus.COMPLETED)).scalars().all()

    # Outer join
    users_with_maybe_orders = session.execute(select(User)).scalars().all()

    # Multiple joins
    users_products = session.execute(select(User).where(Product.is_active == True)).scalars().all()

    # Join with aliased tables
    manager = aliased(User, name="manager")
    users_with_managers = session.execute(select(User)).scalars().all()

    # ==========================================================================
    # SUBQUERIES
    # ==========================================================================

    # Subquery for filtering
    high_spenders_subquery = (
        session.query(Order.user_id)
        .filter(Order.total > 1000)
        .group_by(Order.user_id)
        .subquery()
    )

    high_spending_users = session.execute(select(User).where(User.id.in_(session.query(high_spenders_subquery.c.user_id)))).scalars().all()

    # Correlated subquery
    order_count_subq = (
        session.query(func.count(Order.id))
        .filter(Order.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )

    users_with_order_count = session.execute(select(User)).scalars().all()

    # ==========================================================================
    # COMMON TABLE EXPRESSIONS (CTEs)
    # ==========================================================================

    # CTE for hierarchical query
    category_cte = (
        session.query(
            Category.id,
            Category.name,
            Category.parent_id,
            literal_column("0").label("level"),
        )
        .filter(Category.parent_id == None)
        .cte(name="category_tree", recursive=True)
    )

    category_alias = aliased(Category)
    cte_alias = category_cte.alias()

    recursive_part = (
        session.query(
            category_alias.id,
            category_alias.name,
            category_alias.parent_id,
            (cte_alias.c.level + 1).label("level"),
        )
        .join(cte_alias, category_alias.parent_id == cte_alias.c.id)
    )

    category_tree = category_cte.union_all(recursive_part)

    # ==========================================================================
    # AGGREGATIONS
    # ==========================================================================

    # Group by with aggregates
    sales_by_user = session.execute(select(User.id)).scalars().all()

    # Aggregate functions
    stats = session.execute(select(func.count(Product.id))).scalars().first()

    # ==========================================================================
    # POLYMORPHIC QUERIES
    # ==========================================================================

    # Query polymorphic base
    all_content = session.execute(select(Content)).scalars().all()

    # Query specific subclass
    articles_only = session.execute(select(Article)).scalars().all()

    # Query with polymorphic loading
    content_with_subclasses = session.execute(select(with_polymorphic(Content, [Article, Video]))).scalars().all()

    # ==========================================================================
    # EAGER LOADING
    # ==========================================================================

    # Joined load
    users_eager_addresses = (
        session.query(User)
        .options(joinedload(User.addresses))
        .all()
    )

    # Select in load
    users_eager_orders = (
        session.query(User)
        .options(selectinload(User.orders))
        .all()
    )

    # Subquery load
    users_eager_reviews = (
        session.query(User)
        .options(subqueryload(User.reviews))
        .all()
    )

    # Contains eager with explicit join
    users_with_recent_orders = (
        session.query(User)
        .join(User.orders)
        .filter(Order.created_at > datetime(2024, 1, 1))
        .options(contains_eager(User.orders))
        .all()
    )

    # ==========================================================================
    # HYBRID PROPERTY QUERIES
    # ==========================================================================

    # Query using hybrid property
    users_by_full_name = session.execute(select(User).where(User.full_name.like("%John%"))).scalars().all()

    # Query using hybrid method
    admins = session.execute(select(User).where(User.has_role(UserRole.ADMIN))).scalars().all()

    # Products on sale using hybrid
    sale_products = session.execute(select(Product).where(Product.is_on_sale == True)).scalars().all()

    # ==========================================================================
    # UNION QUERIES
    # ==========================================================================

    # Union of queries
    admins_query = session.query(User.id, User.username).filter(User.role == UserRole.ADMIN)
    moderators_query = session.query(User.id, User.username).filter(User.role == UserRole.MODERATOR)

    privileged_users = admins_query.union(moderators_query).all()
    privileged_users_all = admins_query.union_all(moderators_query).all()

    # ==========================================================================
    # EXISTS QUERIES
    # ==========================================================================

    # Users with at least one order
    users_with_orders_exists = session.execute(select(User).where(exists().where(Order.user_id == User.id))).scalars().all()

    # Users without any orders
    users_without_orders = session.execute(select(User).where(not_(exists().where(Order.user_id == User.id)))).scalars().all()

    # ==========================================================================
    # CASE EXPRESSIONS
    # ==========================================================================

    # Case in query
    user_status_labels = session.execute(select(User.id)).scalars().all()


def raw_sql_examples(engine: Any, session: Session) -> None:
    """Examples of raw SQL execution that need migration."""

    # engine.execute() is removed in 2.0
    result = engine.execute(text("SELECT * FROM users"))

    # More complex raw SQL
    result2 = engine.execute(
        text("SELECT u.*, COUNT(o.id) as order_count "
        "FROM users u LEFT JOIN orders o ON u.id = o.user_id "
        "GROUP BY u.id")
    )

    # Raw SQL with parameters (old style)
    result3 = engine.execute(
        text("SELECT * FROM users WHERE role = :role"),
        {"role": "admin"}
    )

    # Session execute with text
    from sqlalchemy import text
    result4 = session.execute(text("SELECT COUNT(*) FROM products"))


def main() -> None:
    """Main entry point for stress test."""
    engine, session = setup_database()

    try:
        complex_query_examples(session)
        raw_sql_examples(engine, session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
