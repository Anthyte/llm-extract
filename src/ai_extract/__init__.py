"""ai-extract: Extract structured data from any AI. Fast. Simple. Reliable.

This library provides fast, reliable JSON extraction from messy AI outputs.

Basic usage:
    >>> from ai_extract import extract_json
    >>> data = extract_json('Here is the JSON: {"key": "value"}')
    >>> print(data)
    {'key': 'value'}

With metadata:
    >>> from ai_extract import extract_json_with_metadata
    >>> result = extract_json_with_metadata('{"key": "value"}')
    >>> print(result.success, result.confidence)
    True 1.0

Extract all JSON blocks:
    >>> data = extract_json('{"a": 1} and {"b": 2}', strategy="all")
    >>> print(data)
    [{'a': 1}, {'b': 2}]
"""

from .parser import extract_json, extract_json_with_metadata
from .types import (
    Candidate,
    ErrorType,
    ExtractError,
    ExtractionMethod,
    ExtractResult,
)

__all__ = [
    # Main API
    "extract_json",
    "extract_json_with_metadata",
    # Types
    "ExtractResult",
    "ExtractError",
    "ExtractionMethod",
    "ErrorType",
    "Candidate",
]
