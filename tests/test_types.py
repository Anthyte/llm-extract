"""Tests for ai_extract.types module."""

import pytest

from ai_extract.types import (
    Candidate,
    ErrorType,
    ExtractError,
    ExtractionMethod,
    ExtractResult,
)


class TestExtractionMethod:
    """Tests for ExtractionMethod enum."""

    def test_all_methods_exist(self) -> None:
        """Test that all extraction methods are defined."""
        assert ExtractionMethod.DIRECT_PARSE.value == "direct_parse"
        assert ExtractionMethod.BRACE_MATCH.value == "brace_match"

    def test_enum_count(self) -> None:
        """Test that we have exactly 2 extraction methods."""
        assert len(ExtractionMethod) == 2


class TestErrorType:
    """Tests for ErrorType enum."""

    def test_all_error_types_exist(self) -> None:
        """Test that all error types are defined."""
        assert ErrorType.NO_JSON_FOUND.value == "no_json_found"
        assert ErrorType.AMBIGUOUS_MULTIPLE.value == "ambiguous_multiple"

    def test_enum_count(self) -> None:
        """Test that we have exactly 2 error types."""
        assert len(ErrorType) == 2


class TestExtractError:
    """Tests for ExtractError exception."""

    def test_basic_creation(self) -> None:
        """Test creating an ExtractError with basic parameters."""
        error = ExtractError("Test message", ErrorType.NO_JSON_FOUND)
        assert error.message == "Test message"
        assert error.error_type == ErrorType.NO_JSON_FOUND
        assert error.position is None
        assert str(error) == "Test message"

    def test_with_position(self) -> None:
        """Test creating an ExtractError with position."""
        error = ExtractError("Test", ErrorType.NO_JSON_FOUND, position=42)
        assert error.position == 42

    def test_repr(self) -> None:
        """Test ExtractError repr."""
        error = ExtractError("Test", ErrorType.NO_JSON_FOUND)
        assert repr(error) == "ExtractError('no_json_found', 'Test')"

    def test_is_exception(self) -> None:
        """Test that ExtractError is a proper exception."""
        error = ExtractError("Test", ErrorType.NO_JSON_FOUND)
        assert isinstance(error, Exception)

        with pytest.raises(ExtractError) as exc_info:
            raise error
        assert exc_info.value.message == "Test"


class TestCandidate:
    """Tests for Candidate dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a Candidate with basic parameters."""
        candidate = Candidate(
            raw='{"key": "value"}',
            method=ExtractionMethod.DIRECT_PARSE,
            start_pos=0,
            end_pos=16,
            parsed_data={"key": "value"},
        )
        assert candidate.raw == '{"key": "value"}'
        assert candidate.method == ExtractionMethod.DIRECT_PARSE
        assert candidate.start_pos == 0
        assert candidate.end_pos == 16
        assert candidate.parsed_data == {"key": "value"}


class TestExtractResult:
    """Tests for ExtractResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful extraction result."""
        result = ExtractResult(
            success=True,
            data={"key": "value"},
        )
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_failed_result(self) -> None:
        """Test creating a failed extraction result."""
        error = ExtractError("No JSON found", ErrorType.NO_JSON_FOUND)
        result = ExtractResult(
            success=False,
            error=error,
        )
        assert result.success is False
        assert result.data is None
        assert result.error == error

    def test_default_values(self) -> None:
        """Test default values for ExtractResult."""
        result = ExtractResult(success=False)
        assert result.data is None
        assert result.error is None
