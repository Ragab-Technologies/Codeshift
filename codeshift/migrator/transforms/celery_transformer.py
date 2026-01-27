"""Celery 4.x to 5.x transformation using LibCST."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer

# Mapping of old uppercase config keys to new lowercase keys
CONFIG_KEY_MAPPINGS = {
    # Result backend and broker
    "CELERY_RESULT_BACKEND": "result_backend",
    "CELERY_BROKER_URL": "broker_url",
    "BROKER_URL": "broker_url",
    # Task settings
    "CELERY_TASK_ALWAYS_EAGER": "task_always_eager",
    "CELERY_TASK_EAGER_PROPAGATES": "task_eager_propagates",
    "CELERY_TASK_IGNORE_RESULT": "task_ignore_result",
    "CELERY_TASK_TRACK_STARTED": "task_track_started",
    "CELERY_TASK_TIME_LIMIT": "task_time_limit",
    "CELERY_TASK_SOFT_TIME_LIMIT": "task_soft_time_limit",
    "CELERY_TASK_ACKS_LATE": "task_acks_late",
    "CELERY_TASK_SERIALIZER": "task_serializer",
    "CELERY_TASK_ANNOTATIONS": "task_annotations",
    # Result settings
    "CELERY_RESULT_SERIALIZER": "result_serializer",
    "CELERY_RESULT_EXPIRES": "result_expires",
    # General settings
    "CELERY_ACCEPT_CONTENT": "accept_content",
    "CELERY_TIMEZONE": "timezone",
    "CELERY_ENABLE_UTC": "enable_utc",
    "CELERY_IMPORTS": "imports",
    "CELERY_INCLUDE": "include",
    # Worker settings (CELERYD_ prefix)
    "CELERYD_CONCURRENCY": "worker_concurrency",
    "CELERYD_PREFETCH_MULTIPLIER": "worker_prefetch_multiplier",
    "CELERYD_MAX_TASKS_PER_CHILD": "worker_max_tasks_per_child",
    "CELERYD_DISABLE_RATE_LIMITS": "worker_disable_rate_limits",
    "CELERYD_TASK_TIME_LIMIT": "worker_task_time_limit",
    "CELERYD_TASK_SOFT_TIME_LIMIT": "worker_task_soft_time_limit",
    # Beat settings
    "CELERY_BEAT_SCHEDULE": "beat_schedule",
    "CELERY_BEAT_SCHEDULER": "beat_scheduler",
    "CELERYBEAT_SCHEDULE": "beat_schedule",
    "CELERYBEAT_SCHEDULER": "beat_scheduler",
}


class CeleryTransformer(BaseTransformer):
    """Transform Celery 4.x code to 5.x."""

    def __init__(self) -> None:
        super().__init__()
        self._needs_shared_task_import = False
        self._needs_task_import = False
        self._has_shared_task_import = False
        self._has_task_import = False
        self._removed_celery_task_import = False
        self._removed_celery_decorators_import = False

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform Celery imports."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)

        # Handle celery.task module (removed in 5.0)
        if module_name == "celery.task":
            return self._transform_celery_task_import(updated_node)

        # Handle celery.decorators module (removed in 5.0)
        if module_name == "celery.decorators":
            return self._transform_celery_decorators_import(updated_node)

        # Handle celery.task.schedules -> celery.schedules
        if module_name == "celery.task.schedules":
            return self._transform_schedules_import(updated_node)

        # Handle celery.utils.encoding -> kombu.utils.encoding
        if module_name == "celery.utils.encoding":
            return self._transform_encoding_import(updated_node)

        # Track existing celery imports
        if module_name == "celery":
            self._track_celery_imports(updated_node)

        return updated_node

    def _transform_celery_task_import(
        self, node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform imports from celery.task module."""
        if isinstance(node.names, cst.ImportStar):
            self.record_change(
                description="Remove 'from celery.task import *' (module removed)",
                line_number=1,
                original="from celery.task import *",
                replacement="from celery import shared_task, Task",
                transform_name="import_celery_task_star",
            )
            self._needs_shared_task_import = True
            self._needs_task_import = True
            self._removed_celery_task_import = True
            return cst.RemovalSentinel.REMOVE

        imports_to_add_to_celery: list[str] = []

        for name in node.names:
            if isinstance(name, cst.ImportAlias) and isinstance(name.name, cst.Name):
                imported_name = name.name.value

                if imported_name == "Task":
                    # from celery.task import Task -> from celery import Task
                    imports_to_add_to_celery.append("Task")
                    self._needs_task_import = True
                    self.record_change(
                        description="Change 'from celery.task import Task' to 'from celery import Task'",
                        line_number=1,
                        original="from celery.task import Task",
                        replacement="from celery import Task",
                        transform_name="import_task_class",
                    )
                elif imported_name == "task":
                    # from celery.task import task -> from celery import shared_task
                    imports_to_add_to_celery.append("shared_task")
                    self._needs_shared_task_import = True
                    self.record_change(
                        description="Change 'from celery.task import task' to 'from celery import shared_task'",
                        line_number=1,
                        original="from celery.task import task",
                        replacement="from celery import shared_task",
                        transform_name="import_task_decorator",
                    )
                elif imported_name == "periodic_task":
                    # periodic_task is removed, but we still need to signal this
                    self.record_change(
                        description="Remove 'periodic_task' import (use beat_schedule config instead)",
                        line_number=1,
                        original="from celery.task import periodic_task",
                        replacement="# Configure periodic tasks via beat_schedule",
                        transform_name="import_periodic_task_removed",
                        confidence=0.8,
                        notes="periodic_task decorator removed; use beat_schedule configuration",
                    )
                else:
                    # Keep other imports but they will need to come from celery
                    imports_to_add_to_celery.append(imported_name)

        self._removed_celery_task_import = True

        # Remove this import line entirely; imports will be added to celery
        return cst.RemovalSentinel.REMOVE

    def _transform_celery_decorators_import(
        self, node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform imports from celery.decorators module."""
        if isinstance(node.names, cst.ImportStar):
            self.record_change(
                description="Remove 'from celery.decorators import *' (module removed)",
                line_number=1,
                original="from celery.decorators import *",
                replacement="from celery import shared_task",
                transform_name="import_celery_decorators_star",
            )
            self._needs_shared_task_import = True
            self._removed_celery_decorators_import = True
            return cst.RemovalSentinel.REMOVE

        for name in node.names:
            if isinstance(name, cst.ImportAlias) and isinstance(name.name, cst.Name):
                imported_name = name.name.value

                if imported_name == "task":
                    self._needs_shared_task_import = True
                    self.record_change(
                        description="Change 'from celery.decorators import task' to 'from celery import shared_task'",
                        line_number=1,
                        original="from celery.decorators import task",
                        replacement="from celery import shared_task",
                        transform_name="import_decorators_task",
                    )
                elif imported_name == "periodic_task":
                    self.record_change(
                        description="Remove 'periodic_task' import (use beat_schedule config instead)",
                        line_number=1,
                        original="from celery.decorators import periodic_task",
                        replacement="# Configure periodic tasks via beat_schedule",
                        transform_name="import_periodic_task_removed",
                        confidence=0.8,
                    )

        self._removed_celery_decorators_import = True
        return cst.RemovalSentinel.REMOVE

    def _transform_schedules_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform celery.task.schedules -> celery.schedules."""
        self.record_change(
            description="Change 'celery.task.schedules' to 'celery.schedules'",
            line_number=1,
            original="from celery.task.schedules import ...",
            replacement="from celery.schedules import ...",
            transform_name="import_schedules",
        )

        # Change module path
        new_module = cst.Attribute(
            value=cst.Name("celery"),
            attr=cst.Name("schedules"),
        )
        return node.with_changes(module=new_module)

    def _transform_encoding_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Transform celery.utils.encoding -> kombu.utils.encoding."""
        self.record_change(
            description="Change 'celery.utils.encoding' to 'kombu.utils.encoding'",
            line_number=1,
            original="from celery.utils.encoding import ...",
            replacement="from kombu.utils.encoding import ...",
            transform_name="import_utils_encoding",
        )

        # Change module path to kombu.utils.encoding
        new_module = cst.Attribute(
            value=cst.Attribute(
                value=cst.Name("kombu"),
                attr=cst.Name("utils"),
            ),
            attr=cst.Name("encoding"),
        )
        return node.with_changes(module=new_module)

    def _track_celery_imports(self, node: cst.ImportFrom) -> None:
        """Track what's already imported from celery."""
        if isinstance(node.names, cst.ImportStar):
            self._has_shared_task_import = True
            self._has_task_import = True
            return

        for name in node.names:
            if isinstance(name, cst.ImportAlias) and isinstance(name.name, cst.Name):
                if name.name.value == "shared_task":
                    self._has_shared_task_import = True
                elif name.name.value == "Task":
                    self._has_task_import = True

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        """Transform configuration assignments with old uppercase names."""
        # Check for simple name assignments like CELERY_RESULT_BACKEND = "..."
        for target in updated_node.targets:
            if isinstance(target.target, cst.Name):
                var_name = target.target.value
                if var_name in CONFIG_KEY_MAPPINGS:
                    new_name = CONFIG_KEY_MAPPINGS[var_name]
                    self.record_change(
                        description=f"Rename config '{var_name}' to '{new_name}'",
                        line_number=1,
                        original=f"{var_name} = ...",
                        replacement=f"{new_name} = ...",
                        transform_name=f"config_{new_name}",
                    )
                    # Update the target name
                    new_targets = []
                    for t in updated_node.targets:
                        if isinstance(t.target, cst.Name) and t.target.value == var_name:
                            new_targets.append(t.with_changes(target=cst.Name(new_name)))
                        else:
                            new_targets.append(t)
                    return updated_node.with_changes(targets=new_targets)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform attribute access like app.conf.CELERY_RESULT_BACKEND."""
        attr_name = updated_node.attr.value

        # Check if this is a config key that needs renaming
        if attr_name in CONFIG_KEY_MAPPINGS:
            new_name = CONFIG_KEY_MAPPINGS[attr_name]
            self.record_change(
                description=f"Rename config attribute '{attr_name}' to '{new_name}'",
                line_number=1,
                original=f".{attr_name}",
                replacement=f".{new_name}",
                transform_name=f"attr_{new_name}",
            )
            return updated_node.with_changes(attr=cst.Name(new_name))

        return updated_node

    def leave_Subscript(
        self, original_node: cst.Subscript, updated_node: cst.Subscript
    ) -> cst.BaseExpression:
        """Transform subscript access like app.conf['CELERY_RESULT_BACKEND']."""
        # Check if this is a string subscript with a config key
        if len(updated_node.slice) == 1:
            slice_elem = updated_node.slice[0]
            if isinstance(slice_elem, cst.SubscriptElement):
                if isinstance(slice_elem.slice, cst.Index):
                    index_value = slice_elem.slice.value
                    if isinstance(index_value, cst.SimpleString):
                        # Extract the string value (remove quotes)
                        key = index_value.value[1:-1]
                        if key in CONFIG_KEY_MAPPINGS:
                            new_key = CONFIG_KEY_MAPPINGS[key]
                            quote_char = index_value.value[0]
                            new_string = cst.SimpleString(f"{quote_char}{new_key}{quote_char}")
                            new_index = cst.Index(value=new_string)
                            new_slice = [cst.SubscriptElement(slice=new_index)]

                            self.record_change(
                                description=f"Rename config key '{key}' to '{new_key}'",
                                line_number=1,
                                original=f"['{key}']",
                                replacement=f"['{new_key}']",
                                transform_name=f"subscript_{new_key}",
                            )

                            return updated_node.with_changes(slice=new_slice)

        return updated_node

    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> cst.Decorator:
        """Transform @task decorator to @shared_task if imported from removed modules."""
        # Check if the decorator is @task (from celery.task or celery.decorators)
        if isinstance(updated_node.decorator, cst.Name):
            if updated_node.decorator.value == "task":
                # If we removed celery.task or celery.decorators import, rename to shared_task
                if self._removed_celery_task_import or self._removed_celery_decorators_import:
                    self.record_change(
                        description="Rename @task decorator to @shared_task",
                        line_number=1,
                        original="@task",
                        replacement="@shared_task",
                        transform_name="decorator_task_to_shared_task",
                    )
                    return updated_node.with_changes(decorator=cst.Name("shared_task"))

        elif isinstance(updated_node.decorator, cst.Call):
            if isinstance(updated_node.decorator.func, cst.Name):
                if updated_node.decorator.func.value == "task":
                    if self._removed_celery_task_import or self._removed_celery_decorators_import:
                        self.record_change(
                            description="Rename @task(...) decorator to @shared_task(...)",
                            line_number=1,
                            original="@task(...)",
                            replacement="@shared_task(...)",
                            transform_name="decorator_task_to_shared_task",
                        )
                        new_call = updated_node.decorator.with_changes(func=cst.Name("shared_task"))
                        return updated_node.with_changes(decorator=new_call)

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


class CeleryImportTransformer(BaseTransformer):
    """Separate transformer for adding missing Celery imports.

    This runs after the main transformer to add any missing imports.
    """

    def __init__(
        self,
        needs_shared_task_import: bool = False,
        needs_task_import: bool = False,
        has_shared_task_import: bool = False,
        has_task_import: bool = False,
    ) -> None:
        super().__init__()
        self._needs_shared_task_import = needs_shared_task_import
        self._needs_task_import = needs_task_import
        self._has_shared_task_import = has_shared_task_import
        self._has_task_import = has_task_import
        self._found_celery_import = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Check existing celery imports."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)
        if module_name == "celery":
            self._found_celery_import = True
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias) and isinstance(name.name, cst.Name):
                        if name.name.value == "shared_task":
                            self._has_shared_task_import = True
                        elif name.name.value == "Task":
                            self._has_task_import = True

        return True

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Add missing imports to celery import statement."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)
        if module_name != "celery":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = list(updated_node.names)
        changed = False

        if self._needs_shared_task_import and not self._has_shared_task_import:
            new_names.append(cst.ImportAlias(name=cst.Name("shared_task")))
            self._has_shared_task_import = True
            changed = True

            self.record_change(
                description="Add 'shared_task' import",
                line_number=1,
                original="from celery import ...",
                replacement="from celery import ..., shared_task",
                transform_name="add_shared_task_import",
            )

        if self._needs_task_import and not self._has_task_import:
            new_names.append(cst.ImportAlias(name=cst.Name("Task")))
            self._has_task_import = True
            changed = True

            self.record_change(
                description="Add 'Task' import",
                line_number=1,
                original="from celery import ...",
                replacement="from celery import ..., Task",
                transform_name="add_task_import",
            )

        if changed:
            return updated_node.with_changes(names=new_names)

        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add celery import if not found but needed."""
        if self._found_celery_import:
            return updated_node

        needs_import = (self._needs_shared_task_import and not self._has_shared_task_import) or (
            self._needs_task_import and not self._has_task_import
        )

        if not needs_import:
            return updated_node

        # Build the import names
        import_names = []
        if self._needs_shared_task_import and not self._has_shared_task_import:
            import_names.append(cst.ImportAlias(name=cst.Name("shared_task")))
            self.record_change(
                description="Add 'shared_task' import from celery",
                line_number=1,
                original="",
                replacement="from celery import shared_task",
                transform_name="add_shared_task_import",
            )
        if self._needs_task_import and not self._has_task_import:
            import_names.append(cst.ImportAlias(name=cst.Name("Task")))
            self.record_change(
                description="Add 'Task' import from celery",
                line_number=1,
                original="",
                replacement="from celery import Task",
                transform_name="add_task_import",
            )

        if not import_names:
            return updated_node

        # Create the import statement
        new_import = cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=cst.Name("celery"),
                    names=import_names,
                )
            ]
        )

        # Add at the beginning of the module
        new_body = [new_import] + list(updated_node.body)
        return updated_node.with_changes(body=new_body)

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


def transform_celery(source_code: str) -> tuple[str, list]:
    """Transform Celery code from 4.x to 5.x.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = CeleryTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)

        # Second pass: add missing imports
        import_transformer = CeleryImportTransformer(
            needs_shared_task_import=transformer._needs_shared_task_import,
            needs_task_import=transformer._needs_task_import,
            has_shared_task_import=transformer._has_shared_task_import,
            has_task_import=transformer._has_task_import,
        )
        final_tree = transformed_tree.visit(import_transformer)

        all_changes = transformer.changes + import_transformer.changes
        return final_tree.code, all_changes
    except Exception:
        return source_code, []
