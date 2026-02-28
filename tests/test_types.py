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
        assert ExtractionMethod.MARKDOWN_FENCE.value == "markdown_fence"
        assert ExtractionMethod.BRACE_MATCH.value == "brace_match"
        assert ExtractionMethod.HEURISTIC.value == "heuristic"

    def test_enum_count(self) -> None:
        """Test that we have exactly 4 extraction methods."""
        assert len(ExtractionMethod) == 4


class TestErrorType:
    """Tests for ErrorType enum."""

    def test_all_error_types_exist(self) -> None:
        """Test that all error types are defined."""
        assert ErrorType.NO_JSON_FOUND.value == "no_json_found"
        assert ErrorType.INVALID_JSON.value == "invalid_json"
        assert ErrorType.TRUNCATED_JSON.value == "truncated_json"
        assert ErrorType.AMBIGUOUS_MULTIPLE.value == "ambiguous_multiple"
        assert ErrorType.REPAIR_FAILED.value == "repair_failed"

    def test_enum_count(self) -> None:
        """Test that we have exactly 5 error types."""
        assert len(ErrorType) == 5


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
        error = ExtractError("Test", ErrorType.INVALID_JSON, position=42)
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
            start_pos=0,
            end_pos=16,
            method=ExtractionMethod.DIRECT_PARSE,
            confidence=0.9,
        )
        assert candidate.raw == '{"key": "value"}'
        assert candidate.start_pos == 0
        assert candidate.end_pos == 16
        assert candidate.method == ExtractionMethod.DIRECT_PARSE
        assert candidate.confidence == 0.9

    def test_confidence_validation_low(self) -> None:
        """Test that confidence below 0 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            Candidate(
                raw="{}",
                start_pos=0,
                end_pos=2,
                method=ExtractionMethod.BRACE_MATCH,
                confidence=-0.1,
            )

    def test_confidence_validation_high(self) -> None:
        """Test that confidence above 1 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            Candidate(
                raw="{}",
                start_pos=0,
                end_pos=2,
                method=ExtractionMethod.BRACE_MATCH,
                confidence=1.1,
            )

    def test_confidence_boundary_values(self) -> None:
        """Test that confidence at boundary values works."""
        # Confidence of 0.0 should work
        candidate_low = Candidate(
            raw="{}",
            start_pos=0,
            end_pos=2,
            method=ExtractionMethod.HEURISTIC,
            confidence=0.0,
        )
        assert candidate_low.confidence == 0.0

        # Confidence of 1.0 should work
        candidate_high = Candidate(
            raw="{}",
            start_pos=0,
            end_pos=2,
            method=ExtractionMethod.DIRECT_PARSE,
            confidence=1.0,
        )
        assert candidate_high.confidence == 1.0


class TestExtractResult:
    """Tests for ExtractResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful extraction result."""
        result = ExtractResult(
            success=True,
            data={"key": "value"},
            raw_json='{"key": "value"}',
            confidence=0.95,
            method=ExtractionMethod.MARKDOWN_FENCE,
            repairs_applied=["trailing_comma_removal"],
            candidates_found=2,
        )
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.raw_json == '{"key": "value"}'
        assert result.confidence == 0.95
        assert result.method == ExtractionMethod.MARKDOWN_FENCE
        assert result.repairs_applied == ["trailing_comma_removal"]
        assert result.candidates_found == 2
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
        assert result.raw_json is None
        assert result.confidence == 0.0
        assert result.method is None
        assert result.repairs_applied == []
        assert result.candidates_found == 0
        assert result.error == error

    def test_default_values(self) -> None:
        """Test default values for ExtractResult."""
        result = ExtractResult(success=False)
        assert result.data is None
        assert result.raw_json is None
        assert result.confidence == 0.0
        assert result.method is None
        assert result.repairs_applied == []
        assert result.candidates_found == 0
        assert result.error is None

    def test_confidence_validation_low(self) -> None:
        """Test that confidence below 0 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ExtractResult(success=True, confidence=-0.5)

    def test_confidence_validation_high(self) -> None:
        """Test that confidence above 1 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ExtractResult(success=True, confidence=1.5)

    def test_repairs_applied_mutable_default(self) -> None:
        """Test that repairs_applied default is not shared between instances."""
        result1 = ExtractResult(success=True)
        result2 = ExtractResult(success=True)
        result1.repairs_applied.append("test")
        assert result2.repairs_applied == []
