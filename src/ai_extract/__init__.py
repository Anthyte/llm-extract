"""ai-extract: Extract structured data from any AI. Fast. Simple. Reliable.

This library provides fast, reliable JSON extraction from messy AI outputs.

Basic usage:
    >>> from ai_extract import extract_json
    >>> data = extract_json('Here is the JSON: {"key": "value"}')
    >>> print(data)
    {'key': 'value'}

Extract all JSON blocks:
    >>> data = extract_json('{"a": 1} and {"b": 2}', strategy="all")
    >>> print(data)
    [{'a': 1}, {'b': 2}]
"""

from .json_core import extract_json
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
    # Types
    "ExtractResult",
    "ExtractError",
    "ExtractionMethod",
    "ErrorType",
    "Candidate",
]
