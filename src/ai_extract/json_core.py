"""Core JSON extraction logic - optimized for speed and simplicity."""

from __future__ import annotations

from typing import Any, Literal

import orjson

from .types import Candidate, ErrorType, ExtractError, ExtractionMethod, ExtractResult

# ============================================================================
# SECTION 1: Shared helpers
# ============================================================================


def _try_direct_parse_candidate(text: str) -> Candidate | None:
    """Try parsing the full input as JSON and return a direct candidate."""
    try:
        parsed_data: Any = orjson.loads(text)
        return Candidate(
            raw=text,
            method=ExtractionMethod.DIRECT_PARSE,
            start_pos=0,
            end_pos=len(text),
            parsed_data=parsed_data,
        )
    except orjson.JSONDecodeError:
        return None


# ============================================================================
# SECTION 2: First strategy helpers
# ============================================================================


def _parse_subtree_first(candidate: Candidate) -> Any | None:
    """Parse candidate first, then recursively parse children on failure."""
    if candidate.parsed_data is not None:
        return candidate.parsed_data

    try:
        candidate.parsed_data = orjson.loads(candidate.raw)
        return candidate.parsed_data
    except orjson.JSONDecodeError:
        pass

    for child in reversed(candidate.children):
        child_data = _parse_subtree_first(child)
        if child_data is not None:
            return child_data

    return None


def _extract_first_streaming(text: str) -> ExtractResult:
    """Stream-first extraction: parse each completed top-level region immediately."""
    region_candidates: list[Candidate] = []
    stack: list[tuple[str, int]] = []
    in_string: bool = False
    escape_next: bool = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue

        if in_string and char == "\\":
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char in "{[":
            stack.append((char, i))
            continue

        if char not in "}]":
            continue

        if not stack:
            continue

        opener, start = stack.pop()
        if (char == "}" and opener != "{") or (char == "]" and opener != "["):
            stack.clear()
            region_candidates.clear()
            continue

        end_pos: int = i + 1
        current_candidate = Candidate(
            raw=text[start:end_pos],
            method=ExtractionMethod.BRACE_MATCH,
            start_pos=start,
            end_pos=end_pos,
            parsed_data=None,
        )

        nested_children: list[Candidate] = []
        while region_candidates:
            tail_candidate: Candidate = region_candidates[-1]
            if tail_candidate.start_pos >= start and tail_candidate.end_pos <= end_pos:
                nested_children.append(region_candidates.pop())
                continue
            break
        current_candidate.children = nested_children

        if stack:
            region_candidates.append(current_candidate)
        else:
            parsed = _parse_subtree_first(current_candidate)
            if parsed is not None:
                return ExtractResult(success=True, data=parsed)

    # End-of-input fallback: try any remaining candidates from unfinished regions,
    # in scan order.
    for candidate in region_candidates:
        parsed = _parse_subtree_first(candidate)
        if parsed is not None:
            return ExtractResult(success=True, data=parsed)

    return ExtractResult(
        success=False,
        error=ExtractError("No JSON structure found in input", ErrorType.NO_JSON_FOUND),
    )


# ============================================================================
# SECTION 3: All strategy helpers
# ============================================================================
def _find_by_braces(text: str) -> list[Candidate]:
    """Find balanced {...} and [...] structures in a single pass.

    This scanner is O(n): each character is visited once while tracking
    nesting depth and string/escape state.
    """
    candidates: list[Candidate] = []
    stack: list[tuple[str, int]] = []
    in_string: bool = False
    escape_next: bool = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue

        if in_string and char == "\\":
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char in "{[":
            stack.append((char, i))
            continue

        if char not in "}]":
            continue

        if not stack:
            continue

        opener, start = stack.pop()
        if (char == "}" and opener != "{") or (char == "]" and opener != "["):
            stack.clear()
            continue
        end: int = i

        # TODO: Extra computation for raw string??
        raw: str = text[start : end + 1]
        end_pos: int = end + 1
        current_candidate = Candidate(
            raw=raw,
            method=ExtractionMethod.BRACE_MATCH,
            start_pos=start,
            end_pos=end_pos,
            parsed_data=None,
        )

        # Keep only maximal candidates for a region:
        # when a larger enclosing span closes, drop its nested subsets.
        nested_children: list[Candidate] = []
        while candidates:
            tail_candidate: Candidate = candidates[-1]
            if tail_candidate.start_pos >= start and tail_candidate.end_pos <= end_pos:
                nested_children.append(candidates.pop())
                continue
            break

        current_candidate.children = nested_children
        candidates.append(current_candidate)

    return candidates


def _find_candidates(text: str) -> list[Candidate]:
    """Find all JSON candidates in text.

    Uses: _find_by_braces

    Strategy:
    1. Try direct parse (fast path for clean JSON)
    2. If fails, use brace matching (for JSON in text)

    Optimization: Direct parse caches parsed data to avoid double parsing.
    Time complexity: O(n) where n is the length of text.
    """
    direct_candidate = _try_direct_parse_candidate(text)
    if direct_candidate is not None:
        return [direct_candidate]

    # Fallback: Find by brace matching
    return _find_by_braces(text)


def _collect_subtree_all(candidate: Candidate, results: list[Any]) -> None:
    """Collect all valid JSON values from a candidate subtree."""
    if candidate.parsed_data is not None:
        results.append(candidate.parsed_data)
        return

    try:
        data: Any = orjson.loads(candidate.raw)
        candidate.parsed_data = data
        results.append(data)
        return
    except orjson.JSONDecodeError:
        pass

    for child in reversed(candidate.children):
        _collect_subtree_all(child, results)


def _parse_all(candidates: list[Candidate]) -> ExtractResult:
    """Parse all valid JSON from candidates.

    Optimization: Uses cached parsed_data if available.
    """
    results: list[Any] = []

    for candidate in candidates:
        _collect_subtree_all(candidate, results)

    if results:
        return ExtractResult(
            success=True,
            data=results,
        )

    return ExtractResult(
        success=False,
        error=ExtractError(
            f"Failed to parse any JSON from {len(candidates)} candidate(s)",
            ErrorType.NO_JSON_FOUND,
        ),
    )


# ============================================================================
# SECTION 4: Internal orchestration
# ============================================================================


def _extract_json_with_metadata(
    text: str,
    *,
    strategy: Literal["first", "all"] = "first",
) -> ExtractResult:
    """Extract JSON from AI output text with detailed metadata.

    Uses: _find_candidates, _extract_first_streaming, _parse_all

    Args:
        text: The text containing JSON to extract.
        strategy: How to handle multiple JSON blocks.

    Returns:
        ExtractResult with extraction details and metadata.

    Examples:
        >>> result = _extract_json_with_metadata('{"key": "value"}')
        >>> result.success
        True
    """
    if not text or not text.strip():
        return ExtractResult(
            success=False,
            error=ExtractError(
                "Empty input text",
                ErrorType.NO_JSON_FOUND,
            ),
        )

    if strategy == "first":
        direct_candidate = _try_direct_parse_candidate(text)
        if direct_candidate is not None:
            return ExtractResult(success=True, data=direct_candidate.parsed_data)
        return _extract_first_streaming(text)

    if strategy == "all":
        candidates: list[Candidate] = _find_candidates(text)
        if not candidates:
            return ExtractResult(
                success=False,
                error=ExtractError(
                    "No JSON structure found in input",
                    ErrorType.NO_JSON_FOUND,
                ),
            )
        return _parse_all(candidates)

    raise ValueError(f"Invalid strategy: {strategy}")


# ============================================================================
# SECTION 5: Public API
# ============================================================================
def extract_json(
    text: str,
    *,
    strategy: Literal["first", "all"] = "first",
    raise_on_error: bool = True,
) -> dict[str, Any] | list[Any] | None:
    """Extract JSON from AI output text.

    Uses: _extract_json_with_metadata

    Args:
        text: The text containing JSON to extract.
        strategy: How to handle multiple JSON blocks:
            - "first": Return the first valid JSON found (default).
            - "all": Return a list of all valid JSON blocks.
        raise_on_error: Whether to raise ExtractError on failure.
            If False, returns None on failure.

    Returns:
        Extracted JSON data (dict or list).
        - For strategy="first": Returns dict or list
        - For strategy="all": Returns list of dicts/lists
        - Returns None if raise_on_error=False and extraction fails

    Raises:
        ExtractError: If extraction fails and raise_on_error is True.

    Examples:
        >>> extract_json('{"key": "value"}')
        {'key': 'value'}

        >>> extract_json('[1, 2, 3]')
        [1, 2, 3]

        >>> extract_json('Here is the JSON: {"a": 1}')
        {'a': 1}

        >>> extract_json('Invalid', raise_on_error=False)
        None
    """
    result: ExtractResult = _extract_json_with_metadata(text, strategy=strategy)

    if result.success:
        return result.data

    if raise_on_error:
        if result.error:
            raise result.error
        raise ExtractError(  # pragma: no cover
            "Failed to extract JSON",
            ErrorType.NO_JSON_FOUND,
        )

    return None
