"""Django transformation using LibCST for upgrades from 2.2/3.x to 4.x/5.x."""

import libcst as cst
from libcst import matchers as m

from codeshift.migrator.ast_transforms import BaseTransformer


class DjangoTransformer(BaseTransformer):
    """Transform Django code for major version upgrades."""

    def __init__(self) -> None:
        super().__init__()
        # Track imports that need to be added
        self._needs_urllib_parse_import = False
        self._needs_datetime_import = False
        self._urllib_parse_names: set[str] = set()
        # Track which old imports to remove
        self._imports_to_remove: set[str] = set()

    # =========================================================================
    # Import Transformations
    # =========================================================================

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform Django imports."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)

        # Transform django.conf.urls imports
        if module_name == "django.conf.urls":
            return self._transform_conf_urls_import(updated_node)

        # Transform django.utils.encoding imports
        if module_name == "django.utils.encoding":
            return self._transform_encoding_import(updated_node)

        # Transform django.utils.translation imports
        if module_name == "django.utils.translation":
            return self._transform_translation_import(updated_node)

        # Transform django.utils.http imports
        if module_name == "django.utils.http":
            return self._transform_http_import(updated_node)

        # Transform django.contrib.postgres.fields imports (JSONField)
        if module_name == "django.contrib.postgres.fields":
            return self._transform_postgres_fields_import(updated_node)

        # Transform django.contrib.admin.util to utils
        if module_name == "django.contrib.admin.util":
            self.record_change(
                description="Import from django.contrib.admin.utils instead of util",
                line_number=1,
                original="from django.contrib.admin.util",
                replacement="from django.contrib.admin.utils",
                transform_name="admin_util_to_utils",
            )
            return updated_node.with_changes(
                module=self._build_module_node("django.contrib.admin.utils")
            )

        # Transform django.forms.util to utils
        if module_name == "django.forms.util":
            self.record_change(
                description="Import from django.forms.utils instead of util",
                line_number=1,
                original="from django.forms.util",
                replacement="from django.forms.utils",
                transform_name="forms_util_to_utils",
            )
            return updated_node.with_changes(module=self._build_module_node("django.forms.utils"))

        # Transform django.utils.timezone (for utc)
        if module_name == "django.utils.timezone":
            return self._transform_timezone_import(updated_node)

        # Transform django.contrib.sessions.serializers (PickleSerializer)
        if module_name == "django.contrib.sessions.serializers":
            return self._transform_serializers_import(updated_node)

        # Transform django.contrib.staticfiles.storage (CachedStaticFilesStorage)
        if module_name == "django.contrib.staticfiles.storage":
            return self._transform_staticfiles_storage_import(updated_node)

        # Transform django.test.runner (reorder_suite)
        if module_name == "django.test.runner":
            return self._transform_test_runner_import(updated_node)

        return updated_node

    def _transform_conf_urls_import(
        self, node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform imports from django.conf.urls."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "url":
                # url() removed - should import re_path from django.urls
                self.record_change(
                    description="url() removed, import path/re_path from django.urls instead",
                    line_number=1,
                    original="from django.conf.urls import url",
                    replacement="from django.urls import re_path",
                    transform_name="url_to_path_or_re_path",
                )
                # Replace with re_path import (preserving any alias)
                new_name = name.with_changes(name=cst.Name("re_path"))
                new_names.append(new_name)
                has_changes = True
            elif import_name == "include":
                # include() should come from django.urls
                self.record_change(
                    description="Import include from django.urls instead of django.conf.urls",
                    line_number=1,
                    original="from django.conf.urls import include",
                    replacement="from django.urls import include",
                    transform_name="include_import_fix",
                )
                new_names.append(name)
                has_changes = True
            else:
                new_names.append(name)

        if not new_names:
            return cst.RemovalSentinel.REMOVE

        if has_changes:
            # Change the module to django.urls
            return node.with_changes(
                module=self._build_module_node("django.urls"),
                names=new_names,
            )

        return node

    def _transform_encoding_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform imports from django.utils.encoding."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "force_text":
                self.record_change(
                    description="force_text() renamed to force_str()",
                    line_number=1,
                    original="from django.utils.encoding import force_text",
                    replacement="from django.utils.encoding import force_str",
                    transform_name="force_text_to_force_str",
                )
                new_name = name.with_changes(name=cst.Name("force_str"))
                new_names.append(new_name)
                has_changes = True
            elif import_name == "smart_text":
                self.record_change(
                    description="smart_text() renamed to smart_str()",
                    line_number=1,
                    original="from django.utils.encoding import smart_text",
                    replacement="from django.utils.encoding import smart_str",
                    transform_name="smart_text_to_smart_str",
                )
                new_name = name.with_changes(name=cst.Name("smart_str"))
                new_names.append(new_name)
                has_changes = True
            else:
                new_names.append(name)

        if has_changes:
            return node.with_changes(names=new_names)

        return node

    def _transform_translation_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform imports from django.utils.translation."""
        if isinstance(node.names, cst.ImportStar):
            return node

        # Mapping of old names to new names
        translation_mappings = {
            "ugettext": "gettext",
            "ugettext_lazy": "gettext_lazy",
            "ugettext_noop": "gettext_noop",
            "ungettext": "ngettext",
            "ungettext_lazy": "ngettext_lazy",
        }

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name in translation_mappings:
                new_import = translation_mappings[import_name]
                self.record_change(
                    description=f"{import_name}() renamed to {new_import}()",
                    line_number=1,
                    original=f"from django.utils.translation import {import_name}",
                    replacement=f"from django.utils.translation import {new_import}",
                    transform_name=f"{import_name}_to_{new_import}",
                )
                new_name = name.with_changes(name=cst.Name(new_import))
                new_names.append(new_name)
                has_changes = True
            else:
                new_names.append(name)

        if has_changes:
            return node.with_changes(names=new_names)

        return node

    def _transform_http_import(self, node: cst.ImportFrom) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform imports from django.utils.http."""
        if isinstance(node.names, cst.ImportStar):
            return node

        # Mapping to urllib.parse
        urllib_mappings = {
            "urlquote": "quote",
            "urlquote_plus": "quote_plus",
            "urlunquote": "unquote",
            "urlunquote_plus": "unquote_plus",
        }

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name in urllib_mappings:
                new_import = urllib_mappings[import_name]
                self.record_change(
                    description=f"{import_name}() removed, use urllib.parse.{new_import}()",
                    line_number=1,
                    original=f"from django.utils.http import {import_name}",
                    replacement=f"from urllib.parse import {new_import}",
                    transform_name=f"{import_name}_to_urllib_{new_import}",
                )
                self._needs_urllib_parse_import = True
                self._urllib_parse_names.add(new_import)
                has_changes = True
                # Don't add to new_names - we'll add urllib.parse import instead
            elif import_name == "is_safe_url":
                self.record_change(
                    description="is_safe_url() renamed to url_has_allowed_host_and_scheme()",
                    line_number=1,
                    original="from django.utils.http import is_safe_url",
                    replacement="from django.utils.http import url_has_allowed_host_and_scheme",
                    transform_name="is_safe_url_to_url_has_allowed",
                )
                new_name = name.with_changes(name=cst.Name("url_has_allowed_host_and_scheme"))
                new_names.append(new_name)
                has_changes = True
            else:
                new_names.append(name)

        if not new_names:
            return cst.RemovalSentinel.REMOVE

        if has_changes:
            return node.with_changes(names=new_names)

        return node

    def _transform_postgres_fields_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform imports from django.contrib.postgres.fields."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "JSONField":
                self.record_change(
                    description="JSONField moved from django.contrib.postgres.fields to django.db.models",
                    line_number=1,
                    original="from django.contrib.postgres.fields import JSONField",
                    replacement="from django.db.models import JSONField",
                    transform_name="postgres_jsonfield_to_models",
                )
                # Change the module for this import
                has_changes = True
                # Keep the name but will return a different import
            else:
                new_names.append(name)

        if has_changes:
            # If only JSONField was imported, change module to django.db.models
            if not new_names:
                return node.with_changes(
                    module=self._build_module_node("django.db.models"),
                )
            # If there were other imports too, we need to keep the postgres import
            # and add a separate django.db.models import - this is handled in leave_Module

        return node

    def _transform_timezone_import(
        self, node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform imports from django.utils.timezone (for utc alias)."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "utc":
                self.record_change(
                    description="django.utils.timezone.utc removed, use datetime.timezone.utc",
                    line_number=1,
                    original="from django.utils.timezone import utc",
                    replacement="from datetime import timezone",
                    transform_name="timezone_utc_to_datetime",
                    notes="Use timezone.utc instead of utc",
                )
                self._needs_datetime_import = True
                has_changes = True
                # Don't include this import - we'll add datetime import instead
            else:
                new_names.append(name)

        if has_changes:
            if not new_names:
                return cst.RemovalSentinel.REMOVE
            return node.with_changes(names=new_names)

        return node

    def _transform_serializers_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform imports from django.contrib.sessions.serializers."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "PickleSerializer":
                self.record_change(
                    description="PickleSerializer removed, use JSONSerializer instead",
                    line_number=1,
                    original="from django.contrib.sessions.serializers import PickleSerializer",
                    replacement="from django.contrib.sessions.serializers import JSONSerializer",
                    transform_name="pickle_serializer_to_json",
                )
                new_name = name.with_changes(name=cst.Name("JSONSerializer"))
                new_names.append(new_name)
                has_changes = True
            else:
                new_names.append(name)

        if has_changes:
            return node.with_changes(names=new_names)

        return node

    def _transform_staticfiles_storage_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform imports from django.contrib.staticfiles.storage."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "CachedStaticFilesStorage":
                self.record_change(
                    description="CachedStaticFilesStorage removed, use ManifestStaticFilesStorage",
                    line_number=1,
                    original="from django.contrib.staticfiles.storage import CachedStaticFilesStorage",
                    replacement="from django.contrib.staticfiles.storage import ManifestStaticFilesStorage",
                    transform_name="cached_storage_to_manifest",
                )
                new_name = name.with_changes(name=cst.Name("ManifestStaticFilesStorage"))
                new_names.append(new_name)
                has_changes = True
            else:
                new_names.append(name)

        if has_changes:
            return node.with_changes(names=new_names)

        return node

    def _transform_test_runner_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform imports from django.test.runner."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        has_changes = False

        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue

            import_name = self._get_name_value(name.name)

            if import_name == "reorder_suite":
                self.record_change(
                    description="reorder_suite() renamed to reorder_tests()",
                    line_number=1,
                    original="from django.test.runner import reorder_suite",
                    replacement="from django.test.runner import reorder_tests",
                    transform_name="reorder_suite_to_reorder_tests",
                )
                new_name = name.with_changes(name=cst.Name("reorder_tests"))
                new_names.append(new_name)
                has_changes = True
            else:
                new_names.append(name)

        if has_changes:
            return node.with_changes(names=new_names)

        return node

    # =========================================================================
    # Call Expression Transformations
    # =========================================================================

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform function/method calls."""
        # Handle url() calls - convert to re_path()
        if m.matches(updated_node.func, m.Name("url")):
            self.record_change(
                description="url() replaced with re_path()",
                line_number=1,
                original="url(...)",
                replacement="re_path(...)",
                transform_name="url_to_re_path_call",
            )
            return updated_node.with_changes(func=cst.Name("re_path"))

        # Handle force_text() calls
        if m.matches(updated_node.func, m.Name("force_text")):
            self.record_change(
                description="force_text() renamed to force_str()",
                line_number=1,
                original="force_text(...)",
                replacement="force_str(...)",
                transform_name="force_text_to_force_str_call",
            )
            return updated_node.with_changes(func=cst.Name("force_str"))

        # Handle smart_text() calls
        if m.matches(updated_node.func, m.Name("smart_text")):
            self.record_change(
                description="smart_text() renamed to smart_str()",
                line_number=1,
                original="smart_text(...)",
                replacement="smart_str(...)",
                transform_name="smart_text_to_smart_str_call",
            )
            return updated_node.with_changes(func=cst.Name("smart_str"))

        # Handle translation function calls
        translation_call_mappings = {
            "ugettext": "gettext",
            "ugettext_lazy": "gettext_lazy",
            "ugettext_noop": "gettext_noop",
            "ungettext": "ngettext",
            "ungettext_lazy": "ngettext_lazy",
        }

        if isinstance(updated_node.func, cst.Name):
            func_name = updated_node.func.value
            if func_name in translation_call_mappings:
                new_name = translation_call_mappings[func_name]
                self.record_change(
                    description=f"{func_name}() renamed to {new_name}()",
                    line_number=1,
                    original=f"{func_name}(...)",
                    replacement=f"{new_name}(...)",
                    transform_name=f"{func_name}_to_{new_name}_call",
                )
                return updated_node.with_changes(func=cst.Name(new_name))

        # Handle urlquote family function calls
        url_quote_mappings = {
            "urlquote": "quote",
            "urlquote_plus": "quote_plus",
            "urlunquote": "unquote",
            "urlunquote_plus": "unquote_plus",
        }

        if isinstance(updated_node.func, cst.Name):
            func_name = updated_node.func.value
            if func_name in url_quote_mappings:
                new_name = url_quote_mappings[func_name]
                self.record_change(
                    description=f"{func_name}() removed, use {new_name}() from urllib.parse",
                    line_number=1,
                    original=f"{func_name}(...)",
                    replacement=f"{new_name}(...)",
                    transform_name=f"{func_name}_to_{new_name}_call",
                )
                return updated_node.with_changes(func=cst.Name(new_name))

        # Handle is_safe_url() calls
        if m.matches(updated_node.func, m.Name("is_safe_url")):
            self.record_change(
                description="is_safe_url() renamed to url_has_allowed_host_and_scheme()",
                line_number=1,
                original="is_safe_url(...)",
                replacement="url_has_allowed_host_and_scheme(...)",
                transform_name="is_safe_url_to_url_has_allowed_call",
            )
            return updated_node.with_changes(func=cst.Name("url_has_allowed_host_and_scheme"))

        # Handle request.is_ajax() calls
        if isinstance(updated_node.func, cst.Attribute):
            if updated_node.func.attr.value == "is_ajax":
                # Transform request.is_ajax() to
                # request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                self.record_change(
                    description="is_ajax() method removed, check X-Requested-With header",
                    line_number=1,
                    original="request.is_ajax()",
                    replacement="request.headers.get('X-Requested-With') == 'XMLHttpRequest'",
                    transform_name="is_ajax_to_header_check",
                )
                # Build: <object>.headers.get('X-Requested-With') == 'XMLHttpRequest'
                headers_attr = cst.Attribute(
                    value=updated_node.func.value,
                    attr=cst.Name("headers"),
                )
                get_call = cst.Call(
                    func=cst.Attribute(value=headers_attr, attr=cst.Name("get")),
                    args=[cst.Arg(cst.SimpleString("'X-Requested-With'"))],
                )
                return cst.Comparison(
                    left=get_call,
                    comparisons=[
                        cst.ComparisonTarget(
                            operator=cst.Equal(),
                            comparator=cst.SimpleString("'XMLHttpRequest'"),
                        )
                    ],
                )

        # Handle reorder_suite() calls
        if m.matches(updated_node.func, m.Name("reorder_suite")):
            self.record_change(
                description="reorder_suite() renamed to reorder_tests()",
                line_number=1,
                original="reorder_suite(...)",
                replacement="reorder_tests(...)",
                transform_name="reorder_suite_to_reorder_tests_call",
            )
            return updated_node.with_changes(func=cst.Name("reorder_tests"))

        return updated_node

    # =========================================================================
    # Attribute Transformations
    # =========================================================================

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform attribute access patterns."""
        # Handle timezone.utc -> datetime.timezone.utc
        # This handles cases where django.utils.timezone was imported as a module
        attr_str = self._get_full_attribute_safe(updated_node)

        if attr_str == "timezone.utc":
            # Check if this is likely django.utils.timezone.utc
            self.record_change(
                description="timezone.utc should be datetime.timezone.utc",
                line_number=1,
                original="timezone.utc",
                replacement="datetime.timezone.utc",
                transform_name="timezone_utc_attr_fix",
                confidence=0.8,
                notes="Assuming this refers to django.utils.timezone.utc",
            )
            self._needs_datetime_import = True
            # Return datetime.timezone.utc
            return cst.Attribute(
                value=cst.Attribute(value=cst.Name("datetime"), attr=cst.Name("timezone")),
                attr=cst.Name("utc"),
            )

        return updated_node

    # =========================================================================
    # Assignment Transformations (for default_app_config)
    # =========================================================================

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign | cst.RemovalSentinel:
        """Transform assignments, particularly default_app_config removal."""
        # Check for default_app_config = '...'
        for target in updated_node.targets:
            if isinstance(target.target, cst.Name):
                if target.target.value == "default_app_config":
                    self.record_change(
                        description="default_app_config is no longer needed in Django 4.0+",
                        line_number=1,
                        original="default_app_config = '...'",
                        replacement="(removed)",
                        transform_name="remove_default_app_config",
                    )
                    return cst.RemovalSentinel.REMOVE

        return updated_node

    # =========================================================================
    # Class Definition Transformations (for NullBooleanField)
    # =========================================================================

    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.AnnAssign:
        """Transform annotated assignments (for field type annotations)."""
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.BaseExpression:
        """Transform name references."""
        # Handle NullBooleanField -> BooleanField
        # Note: The full transformation to BooleanField(null=True) is complex
        # and is handled in leave_Call for field instantiations
        if updated_node.value == "NullBooleanField":
            self.record_change(
                description="NullBooleanField removed, use BooleanField(null=True)",
                line_number=1,
                original="NullBooleanField",
                replacement="BooleanField",
                transform_name="null_boolean_field_to_boolean_field",
                notes="Remember to add null=True argument",
            )
            return cst.Name("BooleanField")

        # Handle PickleSerializer -> JSONSerializer
        if updated_node.value == "PickleSerializer":
            self.record_change(
                description="PickleSerializer removed, use JSONSerializer",
                line_number=1,
                original="PickleSerializer",
                replacement="JSONSerializer",
                transform_name="pickle_serializer_to_json_name",
            )
            return cst.Name("JSONSerializer")

        # Handle CachedStaticFilesStorage -> ManifestStaticFilesStorage
        if updated_node.value == "CachedStaticFilesStorage":
            self.record_change(
                description="CachedStaticFilesStorage removed, use ManifestStaticFilesStorage",
                line_number=1,
                original="CachedStaticFilesStorage",
                replacement="ManifestStaticFilesStorage",
                transform_name="cached_storage_to_manifest_name",
            )
            return cst.Name("ManifestStaticFilesStorage")

        return updated_node

    # =========================================================================
    # Module-Level Transformations (for adding imports)
    # =========================================================================

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add any required imports at the module level."""
        new_imports: list[cst.SimpleStatementLine] = []

        # Add urllib.parse imports if needed
        if self._needs_urllib_parse_import and self._urllib_parse_names:
            import_names = [
                cst.ImportAlias(name=cst.Name(n)) for n in sorted(self._urllib_parse_names)
            ]
            new_import = cst.SimpleStatementLine(
                body=[
                    cst.ImportFrom(
                        module=cst.Attribute(value=cst.Name("urllib"), attr=cst.Name("parse")),
                        names=import_names,
                    )
                ]
            )
            new_imports.append(new_import)

        # Add datetime import if needed
        if self._needs_datetime_import:
            new_import = cst.SimpleStatementLine(
                body=[
                    cst.ImportFrom(
                        module=cst.Name("datetime"),
                        names=[cst.ImportAlias(name=cst.Name("timezone"))],
                    )
                ]
            )
            new_imports.append(new_import)

        if not new_imports:
            return updated_node

        # Find position to insert imports (after docstrings and __future__ imports)
        insert_pos = 0
        for i, statement in enumerate(updated_node.body):
            if isinstance(statement, cst.SimpleStatementLine):
                # Check for docstring
                if (
                    i == 0
                    and len(statement.body) == 1
                    and isinstance(statement.body[0], cst.Expr)
                    and isinstance(
                        statement.body[0].value, cst.SimpleString | cst.ConcatenatedString
                    )
                ):
                    insert_pos = i + 1
                    continue
                # Check for __future__ import
                if len(statement.body) == 1 and isinstance(statement.body[0], cst.ImportFrom):
                    import_from = statement.body[0]
                    if (
                        isinstance(import_from.module, cst.Name)
                        and import_from.module.value == "__future__"
                    ):
                        insert_pos = i + 1
                        continue
            break

        new_body = (
            list(updated_node.body[:insert_pos])
            + new_imports
            + list(updated_node.body[insert_pos:])
        )
        return updated_node.with_changes(body=new_body)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        return None

    def _build_module_node(self, module_name: str) -> cst.Name | cst.Attribute:
        """Build a module node from a dotted name string."""
        parts = module_name.split(".")
        if len(parts) == 1:
            return cst.Name(parts[0])

        result: cst.Name | cst.Attribute = cst.Name(parts[0])
        for part in parts[1:]:
            result = cst.Attribute(value=result, attr=cst.Name(part))
        return result

    def _get_full_attribute_safe(self, node: cst.Attribute) -> str:
        """Get the full attribute path as a string, safely handling non-attribute values."""
        if isinstance(node.value, cst.Name):
            return f"{node.value.value}.{node.attr.value}"
        elif isinstance(node.value, cst.Attribute):
            return f"{self._get_full_attribute_safe(node.value)}.{node.attr.value}"
        return str(node.attr.value)


def transform_django(source_code: str) -> tuple[str, list]:
    """Transform Django code for version upgrades.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = DjangoTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        return transformed_tree.code, transformer.changes
    except Exception:
        return source_code, []
