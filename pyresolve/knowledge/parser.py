"""LLM-based changelog parser for extracting breaking changes."""

import json
import re
from typing import cast

from pyresolve.knowledge.models import (
    BreakingChange,
    ChangeCategory,
    ChangelogSource,
    Confidence,
)
from pyresolve.utils.llm_client import LLMClient, get_llm_client


class ChangelogParser:
    """Parses changelog content using LLM to extract breaking changes."""

    SYSTEM_PROMPT = """You are an expert at analyzing Python library changelogs and migration guides.
Your task is to extract breaking changes from the provided changelog content.

For each breaking change, identify:
1. category: One of "removed", "renamed", "signature_changed", "behavior_changed"
2. old_api: The old API that is affected (function name, class name, parameter, etc.)
3. new_api: The new API to use instead (if applicable, null otherwise)
4. description: A brief description of the change

Focus only on BREAKING changes that would require code modifications.
Do not include new features, bug fixes, or deprecation warnings unless they affect existing code.

Respond with a JSON array of breaking changes. Example:
[
  {
    "category": "renamed",
    "old_api": ".dict()",
    "new_api": ".model_dump()",
    "description": "The .dict() method has been renamed to .model_dump()"
  },
  {
    "category": "removed",
    "old_api": "parse_obj()",
    "new_api": "model_validate()",
    "description": "parse_obj() has been removed, use model_validate() instead"
  }
]

If there are no breaking changes, respond with an empty array: []"""

    def __init__(self, client: LLMClient | None = None):
        """Initialize the parser.

        Args:
            client: LLM client to use. Defaults to singleton.
        """
        self.client = client or get_llm_client()

    @property
    def is_available(self) -> bool:
        """Check if the parser is available (LLM client configured)."""
        return self.client.is_available

    def parse_changelog(
        self,
        source: ChangelogSource,
        package: str,
        from_version: str,
        to_version: str,
    ) -> list[BreakingChange]:
        """Parse a changelog source to extract breaking changes.

        Args:
            source: The changelog source to parse.
            package: Package name.
            from_version: Starting version.
            to_version: Target version.

        Returns:
            List of detected breaking changes.
        """
        if not self.is_available:
            return []

        # Truncate content if too long
        content = source.content
        max_length = 15000  # Leave room for prompts and response
        if len(content) > max_length:
            content = content[:max_length] + "\n\n[Content truncated...]"

        prompt = f"""Analyze the following {source.source_type} for the Python package "{package}".
Extract all breaking changes between version {from_version} and {to_version}.

{source.source_type.upper()} CONTENT:
```
{content}
```

Extract breaking changes as a JSON array:"""

        response = self.client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.0,
        )

        if not response.success:
            return []

        return self._parse_response(response.content, source)

    def parse_multiple_sources(
        self,
        sources: list[ChangelogSource],
        package: str,
        from_version: str,
        to_version: str,
    ) -> list[BreakingChange]:
        """Parse multiple changelog sources and merge results.

        Args:
            sources: List of changelog sources to parse.
            package: Package name.
            from_version: Starting version.
            to_version: Target version.

        Returns:
            Merged list of breaking changes (duplicates removed).
        """
        all_changes: list[BreakingChange] = []
        seen_apis: set[str] = set()

        for source in sources:
            changes = self.parse_changelog(source, package, from_version, to_version)

            for change in changes:
                # Deduplicate by old_api
                if change.old_api not in seen_apis:
                    seen_apis.add(change.old_api)
                    all_changes.append(change)
                else:
                    # Update confidence if we find the same change in a better source
                    for existing in all_changes:
                        if existing.old_api == change.old_api:
                            if change.confidence > existing.confidence:
                                existing.confidence = change.confidence
                                existing.source = change.source
                            break

        return all_changes

    def _parse_response(
        self,
        content: str,
        source: ChangelogSource,
    ) -> list[BreakingChange]:
        """Parse LLM response into BreakingChange objects.

        Args:
            content: Raw LLM response.
            source: The source this was parsed from.

        Returns:
            List of BreakingChange objects.
        """
        # Extract JSON from response
        json_content = self._extract_json(content)
        if not json_content:
            return []

        try:
            data = json.loads(json_content)
            if not isinstance(data, list):
                return []

            # Determine confidence based on source type
            confidence = self._get_source_confidence(source.source_type)

            changes = []
            for item in data:
                if not isinstance(item, dict):
                    continue

                try:
                    category = ChangeCategory(item.get("category", "behavior_changed"))
                except ValueError:
                    category = ChangeCategory.BEHAVIOR_CHANGED

                changes.append(
                    BreakingChange(
                        category=category,
                        old_api=item.get("old_api", ""),
                        new_api=item.get("new_api"),
                        description=item.get("description", ""),
                        confidence=confidence,
                        source=source.url,
                    )
                )

            return changes

        except json.JSONDecodeError:
            return []

    def _extract_json(self, content: str) -> str | None:
        """Extract JSON array from LLM response.

        Args:
            content: Raw LLM response.

        Returns:
            JSON string or None.
        """
        # Try to find JSON array in response
        content = content.strip()

        # Try direct parse first
        if content.startswith("["):
            # Find matching closing bracket
            bracket_count = 0
            for i, char in enumerate(content):
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        return content[: i + 1]

        # Try to find JSON in code blocks
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(code_block_pattern, content)
        for match in matches:
            match_str = cast(str, match).strip()
            if match_str.startswith("["):
                return match_str

        # Try to find bare JSON array
        array_pattern = r"\[[\s\S]*?\]"
        matches = re.findall(array_pattern, content)
        if matches:
            # Return the longest match (likely the full array)
            return cast(str, max(matches, key=len))

        return None

    def _get_source_confidence(self, source_type: str) -> Confidence:
        """Get confidence level based on source type.

        Args:
            source_type: Type of source.

        Returns:
            Confidence level.
        """
        confidence_map = {
            "migration_guide": Confidence.HIGH,
            "release_notes": Confidence.HIGH,
            "changelog": Confidence.MEDIUM,
        }
        return confidence_map.get(source_type, Confidence.LOW)


# Singleton instance
_default_parser: ChangelogParser | None = None


def get_changelog_parser() -> ChangelogParser:
    """Get the default changelog parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = ChangelogParser()
    return _default_parser
