"""Migration engine with tiered approach."""

from pathlib import Path
from typing import Callable, Optional

from pyresolve.knowledge import (
    Confidence,
    GeneratedKnowledgeBase,
    is_tier_1_library,
)
from pyresolve.migrator.ast_transforms import (
    TransformChange,
    TransformResult,
    TransformStatus,
)
from pyresolve.migrator.llm_migrator import LLMMigrator


class MigrationEngine:
    """Orchestrates migrations using a tiered approach.

    Tier 1: Deterministic AST transforms for well-known libraries
    Tier 2: Knowledge base guided migration with LLM assistance
    Tier 3: Pure LLM migration for unknown patterns
    """

    def __init__(
        self,
        llm_migrator: Optional[LLMMigrator] = None,
    ):
        """Initialize the migration engine.

        Args:
            llm_migrator: Optional LLM migrator instance.
        """
        self.llm_migrator = llm_migrator or LLMMigrator()

    def run_migration(
        self,
        code: str,
        file_path: Path,
        library: str,
        old_version: str,
        new_version: str,
        knowledge_base: Optional[GeneratedKnowledgeBase] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> TransformResult:
        """Run migration using the appropriate tier.

        Args:
            code: Source code to migrate.
            file_path: Path to the file being migrated.
            library: Library being upgraded.
            old_version: Current version.
            new_version: Target version.
            knowledge_base: Optional generated knowledge base.
            progress_callback: Optional progress callback.

        Returns:
            TransformResult with migrated code.
        """

        def report(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        # Tier 1: Try deterministic AST transforms for known libraries
        if is_tier_1_library(library):
            report(f"Using Tier 1 (deterministic AST transforms) for {library}")
            result = self._apply_tier1_transform(code, file_path, library)

            if result.status == TransformStatus.SUCCESS:
                return result

            # If partial success, try Tier 2/3 for remaining
            if result.status == TransformStatus.PARTIAL:
                report("Tier 1 partial - attempting Tier 2/3 for remaining changes")
                # Use transformed code as base for next tier
                code = result.transformed_code

        # Tier 2: Knowledge base guided migration
        if knowledge_base and knowledge_base.overall_confidence >= Confidence.MEDIUM:
            report("Using Tier 2 (KB-guided migration)")
            result = self._apply_tier2_transform(
                code,
                file_path,
                library,
                old_version,
                new_version,
                knowledge_base,
            )

            if result.status == TransformStatus.SUCCESS:
                return result

        # Tier 3: Pure LLM migration
        if self.llm_migrator.is_available:
            report("Using Tier 3 (LLM-assisted migration)")
            return self._apply_tier3_transform(
                code,
                file_path,
                library,
                old_version,
                new_version,
            )

        # No migration possible
        return TransformResult(
            file_path=file_path,
            status=TransformStatus.NO_CHANGES,
            original_code=code,
            transformed_code=code,
            errors=["No migration method available"],
        )

    def _apply_tier1_transform(
        self,
        code: str,
        file_path: Path,
        library: str,
    ) -> TransformResult:
        """Apply Tier 1 deterministic AST transforms.

        Args:
            code: Source code to transform.
            file_path: Path to the file.
            library: Library being upgraded.

        Returns:
            TransformResult.
        """
        # Import transformers dynamically based on library
        transform_func = self._get_transform_func(library)

        if transform_func is None:
            return TransformResult(
                file_path=file_path,
                status=TransformStatus.NO_CHANGES,
                original_code=code,
                transformed_code=code,
                errors=[f"No Tier 1 transformer for {library}"],
            )

        try:
            transformed_code, changes = transform_func(code)

            return TransformResult(
                file_path=file_path,
                status=TransformStatus.SUCCESS if changes else TransformStatus.NO_CHANGES,
                original_code=code,
                transformed_code=transformed_code,
                changes=[
                    TransformChange(
                        description=c.description,
                        line_number=c.line_number,
                        original=c.original,
                        replacement=c.replacement,
                        transform_name=c.transform_name,
                        confidence=getattr(c, "confidence", 1.0),
                    )
                    for c in changes
                ],
            )
        except Exception as e:
            return TransformResult(
                file_path=file_path,
                status=TransformStatus.FAILED,
                original_code=code,
                transformed_code=code,
                errors=[f"Tier 1 transform failed: {e}"],
            )

    def _apply_tier2_transform(
        self,
        code: str,
        file_path: Path,
        library: str,
        old_version: str,
        new_version: str,
        knowledge_base: GeneratedKnowledgeBase,
    ) -> TransformResult:
        """Apply Tier 2 knowledge base guided migration.

        Args:
            code: Source code to transform.
            file_path: Path to the file.
            library: Library being upgraded.
            old_version: Current version.
            new_version: Target version.
            knowledge_base: Generated knowledge base.

        Returns:
            TransformResult.
        """
        if not self.llm_migrator.is_available:
            return TransformResult(
                file_path=file_path,
                status=TransformStatus.NO_CHANGES,
                original_code=code,
                transformed_code=code,
                errors=["LLM not available for Tier 2"],
            )

        # Build context from knowledge base
        context_parts = [
            f"Breaking changes for {library} {old_version} -> {new_version}:",
        ]

        for change in knowledge_base.breaking_changes:
            if change.new_api:
                context_parts.append(
                    f"- {change.old_api} -> {change.new_api}: {change.description}"
                )
            else:
                context_parts.append(f"- {change.old_api} (removed): {change.description}")

        context = "\n".join(context_parts)

        # Use LLM with context
        result = self.llm_migrator.migrate(
            code=code,
            library=library,
            from_version=old_version,
            to_version=new_version,
            context=context,
        )

        if result.success:
            return TransformResult(
                file_path=file_path,
                status=TransformStatus.SUCCESS,
                original_code=code,
                transformed_code=result.migrated_code,
                changes=[
                    TransformChange(
                        description="KB-guided LLM migration",
                        line_number=1,
                        original="(various)",
                        replacement="(migrated)",
                        transform_name="tier2_kb_guided",
                        confidence=0.9,
                    )
                ],
            )

        return TransformResult(
            file_path=file_path,
            status=TransformStatus.FAILED,
            original_code=code,
            transformed_code=code,
            errors=[result.error or "Tier 2 migration failed"],
        )

    def _apply_tier3_transform(
        self,
        code: str,
        file_path: Path,
        library: str,
        old_version: str,
        new_version: str,
    ) -> TransformResult:
        """Apply Tier 3 pure LLM migration.

        Args:
            code: Source code to transform.
            file_path: Path to the file.
            library: Library being upgraded.
            old_version: Current version.
            new_version: Target version.

        Returns:
            TransformResult.
        """
        result = self.llm_migrator.migrate(
            code=code,
            library=library,
            from_version=old_version,
            to_version=new_version,
        )

        if result.success:
            return TransformResult(
                file_path=file_path,
                status=TransformStatus.SUCCESS,
                original_code=code,
                transformed_code=result.migrated_code,
                changes=[
                    TransformChange(
                        description="LLM-assisted migration",
                        line_number=1,
                        original="(various)",
                        replacement="(migrated)",
                        transform_name="tier3_llm",
                        confidence=0.7,
                        notes="Review carefully - LLM-generated changes",
                    )
                ],
            )

        return TransformResult(
            file_path=file_path,
            status=TransformStatus.NO_CHANGES,
            original_code=code,
            transformed_code=code,
            errors=[result.error or "Tier 3 migration failed"],
        )

    def _get_transform_func(self, library: str) -> Optional[Callable]:
        """Get the transform function for a library.

        Args:
            library: Library name.

        Returns:
            Transform function or None.
        """
        try:
            if library == "pydantic":
                from pyresolve.migrator.transforms.pydantic_v1_to_v2 import (
                    transform_pydantic_v1_to_v2,
                )

                return transform_pydantic_v1_to_v2
            elif library == "fastapi":
                from pyresolve.migrator.transforms.fastapi_transformer import (
                    transform_fastapi,
                )

                return transform_fastapi
            elif library == "sqlalchemy":
                from pyresolve.migrator.transforms.sqlalchemy_transformer import (
                    transform_sqlalchemy,
                )

                return transform_sqlalchemy
            elif library == "pandas":
                from pyresolve.migrator.transforms.pandas_transformer import (
                    transform_pandas,
                )

                return transform_pandas
            elif library == "requests":
                from pyresolve.migrator.transforms.requests_transformer import (
                    transform_requests,
                )

                return transform_requests
        except ImportError:
            pass

        return None


# Singleton instance
_default_engine: Optional[MigrationEngine] = None


def get_migration_engine() -> MigrationEngine:
    """Get the default migration engine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = MigrationEngine()
    return _default_engine


def run_migration(
    code: str,
    file_path: Path,
    library: str,
    old_version: str,
    new_version: str,
    knowledge_base: Optional[GeneratedKnowledgeBase] = None,
) -> TransformResult:
    """Convenience function to run a migration.

    Args:
        code: Source code to migrate.
        file_path: Path to the file.
        library: Library being upgraded.
        old_version: Current version.
        new_version: Target version.
        knowledge_base: Optional generated knowledge base.

    Returns:
        TransformResult.
    """
    engine = get_migration_engine()
    return engine.run_migration(
        code=code,
        file_path=file_path,
        library=library,
        old_version=old_version,
        new_version=new_version,
        knowledge_base=knowledge_base,
    )
