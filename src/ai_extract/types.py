"""Type definitions for ai-extract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExtractionMethod(Enum):
    """Method used to extract JSON from text."""

    DIRECT_PARSE = "direct_parse"
    BRACE_MATCH = "brace_match"


class ErrorType(Enum):
    """Classification of extraction errors."""

    NO_JSON_FOUND = "no_json_found"
    AMBIGUOUS_MULTIPLE = "ambiguous_multiple"


class ExtractError(Exception):
    """Exception raised when JSON extraction fails."""

    __slots__ = ("message", "error_type", "position")

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


@dataclass(slots=True, eq=False)
class Candidate:
    """A potential JSON extraction candidate.

    `start_pos` and `end_pos` mark the candidate span in the original text
    using a half-open interval: ``[start_pos, end_pos)``.
    `parsed_data` caches decoded JSON when available to avoid re-parsing.
    `children` stores direct nested candidates, if any.
    """

    raw: str
    method: ExtractionMethod
    start_pos: int
    end_pos: int
    parsed_data: Any | None = None
    children: list[Candidate] = field(default_factory=list)


@dataclass(slots=True, eq=False)
class ExtractResult:
    """Result of a JSON extraction attempt with metadata.

    `data` holds the extracted JSON value. For strategy="all", `data` is a
    list containing all successfully parsed JSON values.
    """

    success: bool
    data: Any | None = None
    error: ExtractError | None = None
