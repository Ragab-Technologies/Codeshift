"""
Old Django model patterns that need migration.
Uses deprecated patterns from Django 3.2 that changed in Django 4.x+
"""
from django.db import models
from django.contrib.postgres.fields import JSONField  # Deprecated in Django 3.1+
from django.utils.encoding import python_2_unicode_compatible  # Deprecated

# Old pattern: Using deprecated @python_2_unicode_compatible decorator
@python_2_unicode_compatible
class Article(models.Model):
    """Old model pattern with deprecated features."""
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Deprecated: Using NullBooleanField (removed in Django 4.0)
    is_published = models.NullBooleanField(default=None)
    
    # Deprecated: Using old JSONField from contrib.postgres
    metadata = JSONField(default=dict)  # Should use django.db.models.JSONField
    
    # Old pattern: Using deprecated on_delete behavior
    author = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        # Deprecated: Using null=True without blank=True for ForeignKey
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Deprecated: Using old default_permissions pattern
        default_permissions = ('add', 'change', 'delete')
        # Old pattern
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Category(models.Model):
    """Another old model pattern."""
    name = models.CharField(max_length=100)
    
    # Deprecated: Using deprecated slug field without unique constraint
    slug = models.SlugField()
    
    # Old pattern: Using deprecated get_absolute_url without reverse
    def get_absolute_url(self):
        return '/categories/%s/' % self.slug  # Should use reverse()

    class Meta:
        verbose_name_plural = 'categories'


# Old pattern: Using deprecated Manager.from_queryset pattern
class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

class ArticleManager(models.Manager):
    # Old pattern: Using deprecated get_query_set (renamed to get_queryset in Django 1.6)
    def get_query_set(self):
        return ArticleQuerySet(self.model, using=self._db)
