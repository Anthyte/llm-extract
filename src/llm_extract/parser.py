"""Main parser module that orchestrates extraction, repair, and parsing."""

from __future__ import annotations

from typing import Any, Literal

import orjson

from .extractor import extract_all_candidates, rank_candidates
from .repair import repair_json
from .types import Candidate, ErrorType, ExtractError, ExtractResult


def extract_json(
    text: str,
    *,
    repair: bool = True,
    strategy: Literal["first", "largest", "all"] = "first",
    raise_on_error: bool = True,
) -> Any | list[Any] | None:
    """Extract JSON from LLM output text.

    Args:
        text: The text containing JSON to extract.
        repair: Whether to attempt repairs on malformed JSON.
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
    result = extract_json_with_metadata(text, repair=repair, strategy=strategy)

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
    repair: bool = True,
    strategy: Literal["first", "largest", "all"] = "first",
) -> ExtractResult:
    """Extract JSON from LLM output text with detailed metadata.

    Args:
        text: The text containing JSON to extract.
        repair: Whether to attempt repairs on malformed JSON.
        strategy: How to handle multiple JSON blocks.

    Returns:
        ExtractResult with extraction details and metadata.

    Examples:
        >>> result = extract_json_with_metadata('{"key": "value"}')
        >>> result.success
        True
        >>> result.confidence
        1.0
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
        return _extract_all(candidates, repair)
    elif strategy == "largest":
        candidates = _sort_by_size(candidates)

    return _extract_first_valid(candidates, repair)


def _extract_first_valid(candidates: list[Candidate], repair: bool) -> ExtractResult:
    """Extract the first valid JSON from candidates."""
    candidates = rank_candidates(candidates)
    all_repairs: list[str] = []
    last_error: Exception | None = None

    for candidate in candidates:
        json_str = candidate.raw
        repairs: list[str] = []

        # Try parsing directly first
        try:
            data = orjson.loads(json_str)
            return ExtractResult(
                success=True,
                data=data,
                raw_json=json_str,
                confidence=candidate.confidence,
                method=candidate.method,
                repairs_applied=repairs,
                candidates_found=len(candidates),
            )
        except orjson.JSONDecodeError as e:
            last_error = e
            if not repair:
                continue

        # Try with repairs
        repair_result = repair_json(json_str)
        repairs = repair_result.repairs_applied
        all_repairs.extend(repairs)

        try:
            data = orjson.loads(repair_result.repaired)
            # Adjust confidence if repairs were needed
            adjusted_confidence = candidate.confidence * 0.9 if repairs else candidate.confidence
            # Truncation path requires extractor to find truncated JSON (rare)
            if repair_result.is_truncated:  # pragma: no cover
                adjusted_confidence *= 0.8

            return ExtractResult(
                success=True,
                data=data,
                raw_json=repair_result.repaired,
                confidence=adjusted_confidence,
                method=candidate.method,
                repairs_applied=repairs,
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
        repairs_applied=all_repairs,
        error=ExtractError(
            error_msg,
            ErrorType.INVALID_JSON,
        ),
    )


def _extract_all(candidates: list[Candidate], repair: bool) -> ExtractResult:
    """Extract all valid JSON from candidates."""
    results: list[Any] = []
    all_repairs: list[str] = []
    successful_methods = []
    max_confidence = 0.0

    for candidate in candidates:
        json_str = candidate.raw
        repairs: list[str] = []

        # Try parsing directly
        try:
            data = orjson.loads(json_str)
            results.append(data)
            max_confidence = max(max_confidence, candidate.confidence)
            successful_methods.append(candidate.method)
            continue
        except orjson.JSONDecodeError:
            if not repair:
                continue

        # Try with repairs
        repair_result = repair_json(json_str)
        repairs = repair_result.repairs_applied
        all_repairs.extend(repairs)

        try:
            data = orjson.loads(repair_result.repaired)
            results.append(data)
            adjusted_confidence = candidate.confidence * 0.9 if repairs else candidate.confidence
            max_confidence = max(max_confidence, adjusted_confidence)
            successful_methods.append(candidate.method)
        except orjson.JSONDecodeError:
            continue

    if not results:
        return ExtractResult(
            success=False,
            candidates_found=len(candidates),
            repairs_applied=all_repairs,
            error=ExtractError(
                f"Failed to parse any JSON from {len(candidates)} candidate(s)",
                ErrorType.INVALID_JSON,
            ),
        )

    return ExtractResult(
        success=True,
        data=results,
        confidence=max_confidence,
        method=successful_methods[0] if successful_methods else None,
        repairs_applied=all_repairs,
        candidates_found=len(candidates),
    )


def _sort_by_size(candidates: list[Candidate]) -> list[Candidate]:
    """Sort candidates by size (largest first)."""
    return sorted(candidates, key=lambda c: len(c.raw), reverse=True)
