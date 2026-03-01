"""Main parser module that orchestrates extraction and parsing."""

from __future__ import annotations

from typing import Any, Literal

import orjson

from .extractor import extract_all_candidates, rank_candidates
from .types import Candidate, ErrorType, ExtractError, ExtractResult


def extract_json(
    text: str,
    *,
    strategy: Literal["first", "largest", "all"] = "first",
    raise_on_error: bool = True,
) -> Any | list[Any] | None:
    """Extract JSON from AI output text.

    Args:
        text: The text containing JSON to extract.
        strategy: How to handle multiple JSON blocks:
            - "first": Return the first valid JSON found (default).
            - "largest": Return the largest valid JSON structure.
            - "all": Return a list of all valid JSON blocks.
        raise_on_error: Whether to raise ExtractError on failure.
            If False, returns None on failure.

    Returns:
        Extracted JSON data. If strategy is "all", returns a list.
        Returns None if raise_on_error is False and extraction fails.

    Raises:
        ExtractError: If extraction fails and raise_on_error is True.

    Examples:
        >>> extract_json('{"key": "value"}')
        {'key': 'value'}

        >>> extract_json('Here is the JSON: {"a": 1}')
        {'a': 1}

        >>> extract_json('Invalid', raise_on_error=False)
        None
    """
    result = extract_json_with_metadata(text, strategy=strategy)

    if result.success:
        return result.data

    if raise_on_error:
        if result.error:
            raise result.error
        # This branch is defensive - extract_json_with_metadata always sets error
        raise ExtractError(  # pragma: no cover
            "Failed to extract JSON",
            ErrorType.NO_JSON_FOUND,
        )

    return None


def extract_json_with_metadata(
    text: str,
    *,
    strategy: Literal["first", "largest", "all"] = "first",
) -> ExtractResult:
    """Extract JSON from AI output text with detailed metadata.

    Args:
        text: The text containing JSON to extract.
        strategy: How to handle multiple JSON blocks.

    Returns:
        ExtractResult with extraction details and metadata.

    Examples:
        >>> result = extract_json_with_metadata('{"key": "value"}')
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

    # Extract all candidates
    candidates = extract_all_candidates(text)

    if not candidates:
        return ExtractResult(
            success=False,
            candidates_found=0,
            error=ExtractError(
                "No JSON structure found in input",
                ErrorType.NO_JSON_FOUND,
            ),
        )

    # Apply strategy-specific handling
    if strategy == "all":
        return _extract_all(candidates)
    elif strategy == "largest":
        candidates = _sort_by_size(candidates)

    return _extract_first_valid(candidates)


def _extract_first_valid(candidates: list[Candidate]) -> ExtractResult:
    """Extract the first valid JSON from candidates."""
    candidates = rank_candidates(candidates)
    last_error: Exception | None = None

    for candidate in candidates:
        json_str = candidate.raw

        try:
            data = orjson.loads(json_str)
            return ExtractResult(
                success=True,
                data=data,
                raw_json=json_str,
                method=candidate.method,
                candidates_found=len(candidates),
            )
        except orjson.JSONDecodeError as e:
            last_error = e
            continue

    # All candidates failed
    error_msg = f"Failed to parse JSON from {len(candidates)} candidate(s)"
    if last_error:
        error_msg += f": {last_error}"

    return ExtractResult(
        success=False,
        candidates_found=len(candidates),
        error=ExtractError(
            error_msg,
            ErrorType.INVALID_JSON,
        ),
    )


def _extract_all(candidates: list[Candidate]) -> ExtractResult:
    """Extract all valid JSON from candidates."""
    results: list[Any] = []
    successful_methods = []

    for candidate in candidates:
        json_str = candidate.raw

        try:
            data = orjson.loads(json_str)
            results.append(data)
            successful_methods.append(candidate.method)
            continue
        except orjson.JSONDecodeError:
            continue

    if not results:
        return ExtractResult(
            success=False,
            candidates_found=len(candidates),
            error=ExtractError(
                f"Failed to parse any JSON from {len(candidates)} candidate(s)",
                ErrorType.INVALID_JSON,
            ),
        )

    return ExtractResult(
        success=True,
        data=results,
        method=successful_methods[0] if successful_methods else None,
        candidates_found=len(candidates),
    )


def _sort_by_size(candidates: list[Candidate]) -> list[Candidate]:
    """Sort candidates by size (largest first)."""
    return sorted(candidates, key=lambda c: len(c.raw), reverse=True)
