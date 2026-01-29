"""
Stress test for Django 3.x to 4.x migration.

This is a VERY complex Django application module designed to test the limits of
Codeshift's Django migration capabilities. It includes:

- 10+ models with complex relationships
- QuerySet chaining with annotate, aggregate, subquery
- F expressions and Q objects
- Custom managers and querysets
- Model inheritance (abstract, proxy, multi-table)
- Signals and receivers
- Custom model fields
- Form validation
- Middleware patterns
- URLconf patterns (path, re_path)
- Class-based views with mixins

This file intentionally uses Django 3.x patterns that require migration to Django 4.x.
"""

# ============================================================================
# IMPORTS - Many deprecated Django 3.x import patterns
# ============================================================================

from django.conf.urls import include, url  # Django 3.x: url() deprecated, use path/re_path
from django.contrib.admin.util import flatten_fieldsets  # Django 3.x: util -> utils
from django.contrib.postgres.fields import JSONField  # Django 3.x: moved to django.db.models
from django.db import models
from django.db.models import (
    Avg,
    Case,
    Count,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat, Lower
from django.test.runner import reorder_suite  # Django 4.x: renamed to reorder_tests
from django.utils.encoding import force_text, smart_text  # Django 3.x: _text -> _str
from django.utils.http import (
    is_safe_url,  # Django 3.x: renamed
    urlquote,
    urlquote_plus,
    urlunquote,
    urlunquote_plus,
)
from django.utils.timezone import utc  # Django 4.x: use datetime.timezone.utc
from django.utils.translation import (
    ugettext as _,  # Django 3.x: ugettext -> gettext
)
from django.utils.translation import (
    ugettext_lazy as _l,
)
from django.utils.translation import (
    ungettext,
    ungettext_lazy,
)

# ============================================================================
# CUSTOM MODEL FIELDS
# ============================================================================


class CompressedTextField(models.TextField):
    """Custom field that stores compressed text."""

    description = _("Compressed text field")

    def __init__(self, *args, **kwargs):
        self.compression_level = kwargs.pop("compression_level", 6)
        super().__init__(*args, **kwargs)


class EncryptedCharField(models.CharField):
    """Custom field that stores encrypted characters."""

    description = _l("Encrypted character field")

    def __init__(self, *args, **kwargs):
        self.encryption_key = kwargs.pop("encryption_key", None)
        kwargs.setdefault("max_length", 255)
        super().__init__(*args, **kwargs)


# ============================================================================
# CUSTOM MANAGERS AND QUERYSETS
# ============================================================================


class PublishedQuerySet(models.QuerySet):
    """QuerySet for published content."""

    def published(self):
        return self.filter(is_published=True, published_at__isnull=False)

    def draft(self):
        return self.filter(is_published=False)

    def with_author_stats(self):
        """Complex annotate with subquery."""
        from django.db.models.functions import Coalesce

        author_article_count = (
            Article.objects.filter(author=OuterRef("author"))
            .values("author")
            .annotate(count=Count("id"))
            .values("count")
        )

        return self.annotate(
            author_total_articles=Coalesce(Subquery(author_article_count), Value(0)),
            normalized_title=Lower("title"),
        )


class PublishedManager(models.Manager):
    """Manager for published content."""

    def get_queryset(self):
        return PublishedQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()


class ActiveUserQuerySet(models.QuerySet):
    """QuerySet for active users with complex aggregations."""

    def active(self):
        return self.filter(is_active=True)

    def with_article_stats(self):
        """Complex aggregation with multiple annotations."""
        return self.annotate(
            total_articles=Count("articles"),
            published_articles=Count("articles", filter=Q(articles__is_published=True)),
            total_views=Coalesce(Sum("articles__view_count"), Value(0)),
            avg_article_length=Avg("articles__content_length"),
            latest_article_date=Max("articles__published_at"),
        )

    def prolific_authors(self, min_articles=10):
        """Filter with annotation and F expression."""
        return self.with_article_stats().filter(total_articles__gte=min_articles).order_by(
            F("total_views").desc(nulls_last=True)
        )


class ActiveUserManager(models.Manager):
    def get_queryset(self):
        return ActiveUserQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()


# ============================================================================
# ABSTRACT BASE MODELS
# ============================================================================


class TimeStampedModel(models.Model):
    """Abstract base model with timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Abstract base model with soft delete capability."""

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])


class SEOModel(models.Model):
    """Abstract SEO fields."""

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True


# ============================================================================
# CONCRETE MODELS WITH COMPLEX RELATIONSHIPS
# ============================================================================


class Category(TimeStampedModel):
    """Category with self-referential relationship."""

    name = models.CharField(max_length=100, verbose_name=_("Category Name"))
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    description = models.TextField(blank=True)
    # Using NullBooleanField which is deprecated in Django 4.x
    is_featured = models.NullBooleanField()  # Django 4.x: use BooleanField(null=True)
    metadata = JSONField(default=dict, blank=True)  # PostgreSQL JSONField

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["name"]

    def __str__(self):
        return smart_text(self.name)  # Should become smart_str


class Tag(TimeStampedModel):
    """Simple tag model."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    color = models.CharField(max_length=7, default="#000000")

    def __str__(self):
        return force_text(self.name)  # Should become force_str


class Author(TimeStampedModel, SoftDeleteModel):
    """Author model with custom manager."""

    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="author_profile",
    )
    bio = CompressedTextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    website = models.URLField(blank=True)
    social_links = JSONField(default=dict, blank=True)
    is_verified = models.NullBooleanField()  # Deprecated
    reputation_score = models.IntegerField(default=0)

    objects = ActiveUserManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = _l("Author")
        verbose_name_plural = _l("Authors")

    def __str__(self):
        return smart_text(self.user.get_full_name() or self.user.username)

    def get_display_name(self):
        """Return display name with proper encoding."""
        name = self.user.get_full_name()
        return force_text(name) if name else force_text(self.user.username)


class Article(TimeStampedModel, SoftDeleteModel, SEOModel):
    """Main article model with complex relationships."""

    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("pending", _("Pending Review")),
        ("published", _("Published")),
        ("archived", _("Archived")),
    ]

    title = models.CharField(max_length=200, verbose_name=_("Article Title"))
    slug = models.SlugField(max_length=250, unique=True)
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="articles",
    )
    content = models.TextField()
    content_length = models.IntegerField(default=0, editable=False)
    excerpt = models.TextField(max_length=500, blank=True)
    categories = models.ManyToManyField(Category, related_name="articles")
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
    featured_image = models.ImageField(upload_to="articles/", blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_published = models.BooleanField(default=False)
    is_featured = models.NullBooleanField()  # Deprecated
    published_at = models.DateTimeField(null=True, blank=True)

    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)

    extra_data = JSONField(default=dict, blank=True)

    objects = PublishedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = _("Article")
        verbose_name_plural = _("Articles")
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "is_published"]),
            models.Index(fields=["-published_at"]),
        ]

    def __str__(self):
        return smart_text(self.title)

    def save(self, *args, **kwargs):
        self.content_length = len(self.content)
        super().save(*args, **kwargs)


class Comment(TimeStampedModel, SoftDeleteModel):
    """Comment model with nested comments support."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    content = models.TextField()
    is_approved = models.NullBooleanField()  # Deprecated

    class Meta:
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")
        ordering = ["created_at"]


# ============================================================================
# PROXY MODEL
# ============================================================================


class PublishedArticle(Article):
    """Proxy model for published articles only."""

    class Meta:
        proxy = True
        verbose_name = _("Published Article")
        verbose_name_plural = _("Published Articles")

    def save(self, *args, **kwargs):
        self.is_published = True
        if not self.published_at:
            from django.utils import timezone

            self.published_at = timezone.now()
        super().save(*args, **kwargs)


# ============================================================================
# MULTI-TABLE INHERITANCE
# ============================================================================


class MediaContent(TimeStampedModel):
    """Base model for all media content."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="media/")
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100)


class Image(MediaContent):
    """Image-specific media content."""

    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    alt_text = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("Image")
        verbose_name_plural = _("Images")


class Video(MediaContent):
    """Video-specific media content."""

    duration = models.PositiveIntegerField(default=0)  # in seconds
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True)
    is_transcoded = models.NullBooleanField()  # Deprecated

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")


class Audio(MediaContent):
    """Audio-specific media content."""

    duration = models.PositiveIntegerField(default=0)
    bitrate = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Audio")
        verbose_name_plural = _("Audio Files")


# ============================================================================
# SIGNALS AND RECEIVERS
# ============================================================================

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=Article)
def article_pre_save(sender, instance, **kwargs):
    """Pre-save signal for articles."""
    # Normalize title
    instance.title = force_text(instance.title).strip()

    # Set content length
    instance.content_length = len(instance.content)


@receiver(post_save, sender=Article)
def article_post_save(sender, instance, created, **kwargs):
    """Post-save signal for articles."""
    if created:
        # Log article creation
        message = ugettext("Article '%(title)s' was created") % {"title": instance.title}
        print(smart_text(message))


@receiver(post_delete, sender=Comment)
def comment_post_delete(sender, instance, **kwargs):
    """Update article comment count after comment deletion."""
    # Using deprecated encoding functions
    article_title = force_text(instance.article.title)
    print(ugettext("Comment deleted from article: %(title)s") % {"title": article_title})


# ============================================================================
# COMPLEX QUERYSETS AND AGGREGATIONS
# ============================================================================


def get_trending_articles(days=7):
    """Get trending articles with complex annotations."""
    from datetime import timedelta

    from django.utils import timezone

    cutoff_date = timezone.now() - timedelta(days=days)

    return (
        Article.objects.filter(
            is_published=True,
            published_at__gte=cutoff_date,
        )
        .annotate(
            engagement_score=F("view_count") + F("like_count") * 2 + Count("comments") * 3,
            days_since_published=Value(days)
            - (timezone.now().date() - F("published_at__date")).days,
        )
        .filter(engagement_score__gt=0)
        .order_by("-engagement_score")[:20]
    )


def get_author_statistics():
    """Get comprehensive author statistics."""
    return (
        Author.objects.active()
        .annotate(
            total_articles=Count("articles"),
            published_count=Count("articles", filter=Q(articles__is_published=True)),
            draft_count=Count("articles", filter=Q(articles__is_published=False)),
            total_views=Coalesce(Sum("articles__view_count"), Value(0)),
            total_likes=Coalesce(Sum("articles__like_count"), Value(0)),
            total_comments=Count("articles__comments"),
            avg_views_per_article=Case(
                When(total_articles=0, then=Value(0)),
                default=F("total_views") / F("total_articles"),
            ),
            engagement_rate=Case(
                When(total_views=0, then=Value(0.0)),
                default=(F("total_likes") + F("total_comments")) * 100.0 / F("total_views"),
            ),
        )
        .filter(total_articles__gt=0)
        .order_by("-engagement_rate")
    )


def get_category_tree_with_counts():
    """Get category tree with article counts using subqueries."""
    article_count_subquery = (
        Article.objects.filter(categories=OuterRef("pk"), is_published=True)
        .values("categories")
        .annotate(count=Count("id"))
        .values("count")
    )

    child_count_subquery = (
        Category.objects.filter(parent=OuterRef("pk"))
        .values("parent")
        .annotate(count=Count("id"))
        .values("count")
    )

    return Category.objects.annotate(
        article_count=Coalesce(Subquery(article_count_subquery), Value(0)),
        child_count=Coalesce(Subquery(child_count_subquery), Value(0)),
        full_name=Case(
            When(parent__isnull=True, then=F("name")),
            default=Concat(F("parent__name"), Value(" > "), F("name")),
        ),
    ).select_related("parent")


def search_articles(query, author_id=None, category_ids=None, tags=None, status=None):
    """Complex search with multiple Q objects."""
    filters = Q(is_deleted=False)

    # Text search across multiple fields
    if query:
        text_filter = Q(title__icontains=query) | Q(content__icontains=query) | Q(excerpt__icontains=query)
        filters &= text_filter

    # Author filter
    if author_id:
        filters &= Q(author_id=author_id)

    # Category filter (any of the categories)
    if category_ids:
        filters &= Q(categories__id__in=category_ids)

    # Tag filter (all tags must match)
    if tags:
        for tag in tags:
            filters &= Q(tags__name__iexact=tag)

    # Status filter
    if status:
        if status == "published":
            filters &= Q(is_published=True)
        elif status == "draft":
            filters &= Q(is_published=False, status="draft")
        else:
            filters &= Q(status=status)

    return (
        Article.objects.filter(filters)
        .distinct()
        .select_related("author", "author__user")
        .prefetch_related("categories", "tags")
        .annotate(
            relevance=Case(
                When(title__iexact=query, then=Value(100)) if query else When(pk__isnull=False, then=Value(0)),
                When(title__icontains=query, then=Value(50)) if query else When(pk__isnull=False, then=Value(0)),
                When(excerpt__icontains=query, then=Value(25)) if query else When(pk__isnull=False, then=Value(0)),
                default=Value(10),
            )
        )
        .order_by("-relevance", "-published_at")
    )


# ============================================================================
# FORMS WITH VALIDATION
# ============================================================================

from django import forms
from django.core.exceptions import ValidationError


class ArticleForm(forms.ModelForm):
    """Form for creating/editing articles."""

    class Meta:
        model = Article
        fields = [
            "title",
            "slug",
            "content",
            "excerpt",
            "categories",
            "tags",
            "status",
            "featured_image",
        ]

    def clean_title(self):
        title = self.cleaned_data.get("title")
        # Using deprecated encoding
        return smart_text(title).strip() if title else title

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        # Check for duplicate slugs
        qs = Article.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(ugettext("This slug is already in use."))
        return slug

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        content = cleaned_data.get("content")

        if status == "published" and not content:
            raise ValidationError(
                ugettext("Published articles must have content."),
            )

        return cleaned_data


class CommentForm(forms.ModelForm):
    """Form for adding comments."""

    class Meta:
        model = Comment
        fields = ["content"]

    def clean_content(self):
        content = self.cleaned_data.get("content")
        content = force_text(content).strip()

        if len(content) < 10:
            raise ValidationError(
                ugettext("Comment must be at least 10 characters long."),
            )

        return content


class AuthorRegistrationForm(forms.ModelForm):
    """Form for author registration."""

    class Meta:
        model = Author
        fields = ["bio", "website"]

    def clean_website(self):
        website = self.cleaned_data.get("website")
        if website:
            # Validate URL using deprecated function
            if not is_safe_url(website, allowed_hosts={"example.com"}):
                raise ValidationError(ugettext("Invalid website URL."))
        return website


# ============================================================================
# MIDDLEWARE PATTERNS
# ============================================================================


class RequestLoggingMiddleware:
    """Middleware that logs all requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log request using deprecated encoding
        path = force_text(request.path)
        method = smart_text(request.method)

        # Check for AJAX using deprecated method
        if request.is_ajax():  # Deprecated in Django 3.1+
            print(ugettext("AJAX request: %(method)s %(path)s") % {"method": method, "path": path})
        else:
            print(ugettext("Request: %(method)s %(path)s") % {"method": method, "path": path})

        response = self.get_response(request)
        return response


class SecurityMiddleware:
    """Middleware for security checks."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for safe URL redirects using deprecated function
        next_url = request.GET.get("next")
        if next_url:
            # Using deprecated is_safe_url
            if not is_safe_url(next_url, allowed_hosts={request.get_host()}):
                next_url = "/"

        response = self.get_response(request)
        return response


class LocaleMiddleware:
    """Middleware for locale handling."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Using deprecated timezone.utc
        request.timezone = utc

        response = self.get_response(request)
        return response


# ============================================================================
# CLASS-BASED VIEWS WITH MIXINS
# ============================================================================

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)


class ArticleContextMixin:
    """Mixin to add common article context."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["popular_tags"] = (
            Tag.objects.annotate(article_count=Count("articles")).order_by("-article_count")[:10]
        )
        return context


class SEOMixin:
    """Mixin for SEO meta tags."""

    def get_meta_title(self):
        return smart_text(getattr(self, "meta_title", ""))

    def get_meta_description(self):
        return force_text(getattr(self, "meta_description", ""))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["meta_title"] = self.get_meta_title()
        context["meta_description"] = self.get_meta_description()
        return context


class ArticleListView(ArticleContextMixin, SEOMixin, ListView):
    """List view for articles."""

    model = Article
    template_name = "articles/list.html"
    context_object_name = "articles"
    paginate_by = 20
    meta_title = _l("Articles")

    def get_queryset(self):
        qs = Article.objects.published()

        # Apply filters
        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(categories__slug=category)

        tag = self.request.GET.get("tag")
        if tag:
            qs = qs.filter(tags__slug=tag)

        # Complex annotation
        qs = qs.annotate(
            comment_count=Count("comments", filter=Q(comments__is_approved=True)),
        ).select_related("author", "author__user")

        return qs


class ArticleDetailView(ArticleContextMixin, SEOMixin, DetailView):
    """Detail view for a single article."""

    model = Article
    template_name = "articles/detail.html"
    context_object_name = "article"

    def get_meta_title(self):
        return smart_text(self.object.title)

    def get_meta_description(self):
        return force_text(self.object.excerpt or self.object.content[:160])

    def get_queryset(self):
        return (
            Article.objects.published()
            .select_related("author", "author__user")
            .prefetch_related(
                "categories",
                "tags",
                "comments__author",
            )
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Increment view count using F expression
        Article.objects.filter(pk=obj.pk).update(view_count=F("view_count") + 1)
        return obj


class ArticleCreateView(LoginRequiredMixin, PermissionRequiredMixin, ArticleContextMixin, CreateView):
    """Create view for articles."""

    model = Article
    form_class = ArticleForm
    template_name = "articles/form.html"
    permission_required = "blog.add_article"

    def form_valid(self, form):
        form.instance.author = self.request.user.author_profile
        return super().form_valid(form)


class ArticleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, ArticleContextMixin, UpdateView):
    """Update view for articles."""

    model = Article
    form_class = ArticleForm
    template_name = "articles/form.html"
    permission_required = "blog.change_article"

    def get_queryset(self):
        # Authors can only edit their own articles
        return Article.objects.filter(author__user=self.request.user)


class ArticleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for articles."""

    model = Article
    template_name = "articles/confirm_delete.html"
    permission_required = "blog.delete_article"
    success_url = "/articles/"

    def get_queryset(self):
        return Article.objects.filter(author__user=self.request.user)


# ============================================================================
# URL CONFIGURATION - Using deprecated url() function
# ============================================================================


# This urlpatterns intentionally uses deprecated url() patterns
urlpatterns = [
    # Old-style url() patterns that should be migrated to path() or re_path()
    url(r"^$", ArticleListView.as_view(), name="article_list"),
    url(r"^article/(?P<slug>[\w-]+)/$", ArticleDetailView.as_view(), name="article_detail"),
    url(r"^article/(?P<slug>[\w-]+)/edit/$", ArticleUpdateView.as_view(), name="article_edit"),
    url(r"^article/(?P<slug>[\w-]+)/delete/$", ArticleDeleteView.as_view(), name="article_delete"),
    url(r"^create/$", ArticleCreateView.as_view(), name="article_create"),
    # URL with include
    url(r"^api/", include("api.urls")),
    url(r"^comments/", include("comments.urls", namespace="comments")),
    # Complex regex patterns
    url(
        r"^archive/(?P<year>\d{4})/(?P<month>\d{2})/$",
        ArticleListView.as_view(),
        name="article_archive",
    ),
    url(
        r"^author/(?P<username>[\w.@+-]+)/articles/$",
        ArticleListView.as_view(),
        name="author_articles",
    ),
    url(
        r"^category/(?P<category_slug>[\w-]+)/tag/(?P<tag_slug>[\w-]+)/$",
        ArticleListView.as_view(),
        name="category_tag_articles",
    ),
]


# ============================================================================
# ADMIN CONFIGURATION
# ============================================================================

from django.contrib import admin


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "status", "is_published", "published_at"]
    list_filter = ["status", "is_published", "categories"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    raw_id_fields = ["author"]
    readonly_fields = ["view_count", "like_count", "content_length"]

    fieldsets = (
        (None, {"fields": ("title", "slug", "author")}),
        (_("Content"), {"fields": ("content", "excerpt", "featured_image")}),
        (_("Categorization"), {"fields": ("categories", "tags")}),
        (
            _("Publishing"),
            {"fields": ("status", "is_published", "is_featured", "published_at")},
        ),
        (
            _l("Statistics"),
            {
                "fields": ("view_count", "like_count", "content_length"),
                "classes": ("collapse",),
            },
        ),
        (
            _l("SEO"),
            {
                "fields": ("meta_title", "meta_description", "meta_keywords"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        # Using deprecated admin util function
        fieldsets = super().get_fieldsets(request, obj)
        flattened = flatten_fieldsets(fieldsets)
        return fieldsets


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "is_featured"]
    list_filter = ["is_featured", "parent"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["user", "is_verified", "reputation_score"]
    list_filter = ["is_verified", "is_deleted"]
    search_fields = ["user__username", "user__email"]


# ============================================================================
# UTILITY FUNCTIONS USING DEPRECATED PATTERNS
# ============================================================================


def encode_url_param(param):
    """Encode a URL parameter using deprecated functions."""
    return urlquote(force_text(param))


def decode_url_param(param):
    """Decode a URL parameter using deprecated functions."""
    return urlunquote(smart_text(param))


def encode_url_param_plus(param):
    """Encode a URL parameter with + for spaces."""
    return urlquote_plus(force_text(param))


def decode_url_param_plus(param):
    """Decode a URL parameter with + for spaces."""
    return urlunquote_plus(smart_text(param))


def validate_redirect_url(url, request):
    """Validate a redirect URL using deprecated is_safe_url."""
    return is_safe_url(url, allowed_hosts={request.get_host()})


def get_pluralized_message(count, singular, plural):
    """Get pluralized message using deprecated ungettext."""
    return ungettext(singular, plural, count) % {"count": count}


def get_pluralized_message_lazy(count, singular, plural):
    """Get lazy pluralized message using deprecated ungettext_lazy."""
    return ungettext_lazy(singular, plural, count)


def run_test_suite(suite):
    """Run test suite using deprecated function."""
    # Using deprecated reorder_suite
    reordered = reorder_suite(suite, (None,))
    return reordered


def get_current_utc_time():
    """Get current UTC time using deprecated timezone.utc."""
    from django.utils import timezone

    return timezone.now().replace(tzinfo=utc)


def process_user_input(data):
    """Process user input with encoding functions."""
    if isinstance(data, bytes):
        data = force_text(data)
    return smart_text(data).strip()


# ============================================================================
# APP CONFIGURATION (deprecated default_app_config)
# ============================================================================

# This is deprecated in Django 4.0+
default_app_config = "blog.apps.BlogConfig"
