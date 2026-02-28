"""Type definitions for ai-extract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExtractionMethod(Enum):
    """Method used to extract JSON from text."""

    DIRECT_PARSE = "direct_parse"
    MARKDOWN_FENCE = "markdown_fence"
    BRACE_MATCH = "brace_match"
    HEURISTIC = "heuristic"


class ErrorType(Enum):
    """Classification of extraction errors."""

    NO_JSON_FOUND = "no_json_found"
    INVALID_JSON = "invalid_json"
    TRUNCATED_JSON = "truncated_json"
    AMBIGUOUS_MULTIPLE = "ambiguous_multiple"
    REPAIR_FAILED = "repair_failed"


class ExtractError(Exception):
    """Exception raised when JSON extraction fails."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType,
        position: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.position = position

    def __repr__(self) -> str:
        return f"ExtractError({self.error_type.value!r}, {self.message!r})"


@dataclass
class Candidate:
    """A potential JSON extraction candidate."""

    raw: str
    start_pos: int
    end_pos: int
    method: ExtractionMethod
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class ExtractResult:
    """Result of a JSON extraction attempt with metadata."""

    success: bool
    data: Any | None = None
    raw_json: str | None = None
    confidence: float = 0.0
    method: ExtractionMethod | None = None
    repairs_applied: list[str] = field(default_factory=list)
    candidates_found: int = 0
    error: ExtractError | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
