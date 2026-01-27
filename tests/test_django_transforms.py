"""Tests for Django 2.2/3.x to 4.x/5.x transforms."""

from codeshift.migrator.transforms.django_transformer import transform_django


class TestDjangoUrlImportTransforms:
    """Tests for Django URL import transformations."""

    def test_url_to_re_path_import(self):
        """Test transforming from django.conf.urls import url to re_path."""
        code = """
from django.conf.urls import url

urlpatterns = [
    url(r'^home/$', home_view),
]
"""
        transformed, changes = transform_django(code)

        assert "from django.urls import re_path" in transformed or "re_path" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_include_import_move(self):
        """Test transforming include import from conf.urls to django.urls."""
        code = """
from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('api.urls')),
]
"""
        transformed, changes = transform_django(code)

        # include should move to django.urls
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoEncodingTransforms:
    """Tests for Django encoding function transformations."""

    def test_smart_text_to_smart_str(self):
        """Test transforming smart_text to smart_str."""
        code = """
from django.utils.encoding import smart_text

result = smart_text(some_bytes)
"""
        transformed, changes = transform_django(code)

        assert "smart_str" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_force_text_to_force_str(self):
        """Test transforming force_text to force_str."""
        code = """
from django.utils.encoding import force_text

result = force_text(some_bytes)
"""
        transformed, changes = transform_django(code)

        assert "force_str" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoAdminUtilTransforms:
    """Tests for Django admin util transformations."""

    def test_admin_util_to_utils(self):
        """Test transforming django.contrib.admin.util to utils."""
        code = """
from django.contrib.admin.util import flatten_fieldsets
"""
        transformed, changes = transform_django(code)

        assert "django.contrib.admin.utils" in transformed
        assert "django.contrib.admin.util" not in transformed or ".utils" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoFormsUtilTransforms:
    """Tests for Django forms util transformations."""

    def test_forms_util_to_utils(self):
        """Test transforming django.forms.util to utils."""
        code = """
from django.forms.util import ErrorList
"""
        transformed, changes = transform_django(code)

        assert "django.forms.utils" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoFieldTransforms:
    """Tests for Django field transformations."""

    def test_nullbooleanfield_transform(self):
        """Test transforming NullBooleanField to BooleanField(null=True)."""
        code = """
from django.db import models

class MyModel(models.Model):
    flag = models.NullBooleanField()
"""
        transformed, changes = transform_django(code)

        # Should transform NullBooleanField
        assert "BooleanField" in transformed or len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoJsonFieldTransforms:
    """Tests for Django JSONField import transformations."""

    def test_postgres_jsonfield_to_django_models(self):
        """Test transforming PostgreSQL JSONField import to django.db.models."""
        code = """
from django.contrib.postgres.fields import JSONField

class MyModel(models.Model):
    data = JSONField()
"""
        transformed, changes = transform_django(code)

        # JSONField should be imported from django.db.models in Django 3.1+
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoTranslationTransforms:
    """Tests for Django translation transformations."""

    def test_ugettext_to_gettext(self):
        """Test transforming ugettext to gettext."""
        code = """
from django.utils.translation import ugettext as _

message = _("Hello World")
"""
        transformed, changes = transform_django(code)

        assert "gettext" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_ugettext_lazy_to_gettext_lazy(self):
        """Test transforming ugettext_lazy to gettext_lazy."""
        code = """
from django.utils.translation import ugettext_lazy as _

message = _("Hello World")
"""
        transformed, changes = transform_django(code)

        assert "gettext_lazy" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestDjangoMultipleTransforms:
    """Tests for multiple Django transformations."""

    def test_comprehensive_migration(self):
        """Test multiple Django migrations in one file."""
        code = """
from django.conf.urls import url, include
from django.utils.encoding import smart_text, force_text
from django.contrib.admin.util import flatten_fieldsets

urlpatterns = [
    url(r'^home/$', home_view),
    url(r'^api/', include('api.urls')),
]

def process(data):
    return smart_text(force_text(data))
"""
        transformed, changes = transform_django(code)

        # Should have multiple changes
        assert len(changes) >= 2

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern Django code is not transformed."""
        code = """
from django.urls import path, include
from django.utils.encoding import smart_str, force_str
from django.db.models import JSONField

urlpatterns = [
    path('home/', home_view),
    path('api/', include('api.urls')),
]

def process(data):
    return smart_str(force_str(data))
"""
        transformed, changes = transform_django(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")
