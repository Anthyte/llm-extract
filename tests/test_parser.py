"""Tests for ai_extract.parser module."""

import pytest

from ai_extract import (
    ErrorType,
    ExtractError,
    ExtractionMethod,
    extract_json,
    extract_json_with_metadata,
)


class TestExtractJson:
    """Tests for extract_json function."""

    def test_simple_json_object(self) -> None:
        """Test extracting simple JSON object."""
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_array(self) -> None:
        """Test extracting JSON array."""
        result = extract_json("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_nested_json(self) -> None:
        """Test extracting nested JSON."""
        result = extract_json('{"outer": {"inner": [1, 2, 3]}}')
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_json_in_text(self) -> None:
        """Test extracting JSON from surrounding text."""
        result = extract_json('Here is the JSON: {"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fence(self) -> None:
        """Test extracting from markdown fence."""
        text = """```json
{"key": "value"}
```"""
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_repair_trailing_comma(self) -> None:
        """Test automatic repair of trailing comma."""
        result = extract_json('{"key": "value",}')
        assert result == {"key": "value"}

    def test_repair_disabled(self) -> None:
        """Test that repair can be disabled."""
        with pytest.raises(ExtractError) as exc_info:
            extract_json('{"key": "value",}', repair=False)
        assert exc_info.value.error_type == ErrorType.INVALID_JSON

    def test_no_json_raises(self) -> None:
        """Test that missing JSON raises error."""
        with pytest.raises(ExtractError) as exc_info:
            extract_json("no json here")
        assert exc_info.value.error_type == ErrorType.NO_JSON_FOUND

    def test_no_json_returns_none(self) -> None:
        """Test that missing JSON returns None when raise_on_error=False."""
        result = extract_json("no json here", raise_on_error=False)
        assert result is None

    def test_empty_input(self) -> None:
        """Test that empty input raises error."""
        with pytest.raises(ExtractError) as exc_info:
            extract_json("")
        assert exc_info.value.error_type == ErrorType.NO_JSON_FOUND

    def test_empty_input_returns_none(self) -> None:
        """Test that empty input returns None when raise_on_error=False."""
        result = extract_json("", raise_on_error=False)
        assert result is None

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only input raises error."""
        with pytest.raises(ExtractError):
            extract_json("   ")


class TestExtractJsonStrategy:
    """Tests for extract_json with different strategies."""

    def test_strategy_first(self) -> None:
        """Test 'first' strategy returns first JSON."""
        text = '{"a": 1} and {"b": 2}'
        result = extract_json(text, strategy="first")
        assert result == {"a": 1}

    def test_strategy_largest(self) -> None:
        """Test 'largest' strategy returns largest JSON."""
        text = '{"a": 1} and {"b": 2, "c": 3, "d": 4}'
        result = extract_json(text, strategy="largest")
        assert result == {"b": 2, "c": 3, "d": 4}

    def test_strategy_all(self) -> None:
        """Test 'all' strategy returns all JSON blocks."""
        text = '{"a": 1} and {"b": 2}'
        result = extract_json(text, strategy="all")
        assert isinstance(result, list)
        assert len(result) == 2
        assert {"a": 1} in result
        assert {"b": 2} in result

    def test_strategy_all_single(self) -> None:
        """Test 'all' strategy with single JSON."""
        result = extract_json('{"key": "value"}', strategy="all")
        assert result == [{"key": "value"}]

    def test_strategy_all_with_repair(self) -> None:
        """Test 'all' strategy with repair."""
        text = '{"a": 1,} and {"b": 2,}'
        result = extract_json(text, strategy="all")
        assert len(result) == 2

    def test_strategy_all_no_repair_skip_invalid(self) -> None:
        """Test 'all' strategy with repair=False skips invalid JSON."""
        # First JSON is valid, second needs repair
        text = '{"a": 1} and {"b": 2,}'
        result = extract_json(text, strategy="all", repair=False)
        # Should only get the valid one
        assert len(result) == 1
        assert {"a": 1} in result

    def test_strategy_all_all_fail(self) -> None:
        """Test 'all' strategy when all candidates fail."""
        # Malformed JSON that can't be repaired even with repair=True
        result = extract_json_with_metadata(
            "Here is some {broken: json} text",
            strategy="all",
            repair=False,
        )
        assert result.success is False
        assert result.error is not None


class TestExtractJsonWithMetadata:
    """Tests for extract_json_with_metadata function."""

    def test_successful_extraction(self) -> None:
        """Test successful extraction returns proper metadata."""
        result = extract_json_with_metadata('{"key": "value"}')
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.raw_json == '{"key": "value"}'
        assert result.confidence == 1.0
        assert result.method == ExtractionMethod.DIRECT_PARSE
        assert result.error is None

    def test_markdown_fence_confidence(self) -> None:
        """Test that markdown fence has high confidence."""
        text = """```json
{"key": "value"}
```"""
        result = extract_json_with_metadata(text)
        assert result.success is True
        assert result.confidence >= 0.9
        assert result.method == ExtractionMethod.MARKDOWN_FENCE

    def test_brace_match_confidence(self) -> None:
        """Test that brace match has medium confidence."""
        result = extract_json_with_metadata('Some text {"key": "value"} more text')
        assert result.success is True
        assert 0.7 <= result.confidence <= 0.95
        assert result.method == ExtractionMethod.BRACE_MATCH

    def test_repairs_tracked(self) -> None:
        """Test that repairs are tracked in metadata."""
        result = extract_json_with_metadata('{"key": "value",}')
        assert result.success is True
        assert "trailing_comma_removal" in result.repairs_applied

    def test_confidence_reduced_with_repair(self) -> None:
        """Test that confidence is reduced when repairs are applied."""
        clean = extract_json_with_metadata('{"key": "value"}')
        repaired = extract_json_with_metadata('{"key": "value",}')
        assert clean.confidence > repaired.confidence

    def test_truncated_json_in_repair_result(self) -> None:
        """Test that truncated JSON gets repaired when possible."""
        # Use repair module directly to test truncation handling
        from ai_extract.repair import is_truncated_json, repair_json

        # Verify truncation detection
        assert is_truncated_json('{"key": "value"') is True

        # Verify repair completes it
        result = repair_json('{"key": "value"')
        assert result.is_truncated is True
        assert "}" in result.repaired

    def test_candidates_found_tracked(self) -> None:
        """Test that candidates_found is tracked."""
        result = extract_json_with_metadata('{"a": 1} and {"b": 2}')
        assert result.candidates_found >= 2

    def test_failed_extraction(self) -> None:
        """Test failed extraction returns proper error."""
        result = extract_json_with_metadata("no json")
        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error.error_type == ErrorType.NO_JSON_FOUND

    def test_empty_input(self) -> None:
        """Test empty input returns proper error."""
        result = extract_json_with_metadata("")
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.NO_JSON_FOUND

    def test_invalid_json_error(self) -> None:
        """Test invalid JSON error when repair fails."""
        # Text that looks like JSON but can't be parsed
        result = extract_json_with_metadata('{"key": value_without_quotes}', repair=False)
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.INVALID_JSON


class TestExtractJsonEdgeCases:
    """Tests for edge cases in JSON extraction."""

    def test_unicode_content(self) -> None:
        """Test JSON with unicode content."""
        result = extract_json('{"emoji": "🎉", "chinese": "中文"}')
        assert result == {"emoji": "🎉", "chinese": "中文"}

    def test_escaped_characters(self) -> None:
        """Test JSON with escaped characters."""
        result = extract_json('{"text": "line1\\nline2\\ttab"}')
        assert result == {"text": "line1\nline2\ttab"}

    def test_null_value(self) -> None:
        """Test JSON with null value."""
        result = extract_json('{"key": null}')
        assert result == {"key": None}

    def test_boolean_values(self) -> None:
        """Test JSON with boolean values."""
        result = extract_json('{"yes": true, "no": false}')
        assert result == {"yes": True, "no": False}

    def test_numeric_values(self) -> None:
        """Test JSON with various numeric values."""
        result = extract_json('{"int": 42, "float": 3.14, "neg": -1, "exp": 1e10}')
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["neg"] == -1
        assert result["exp"] == 1e10

    def test_deeply_nested(self) -> None:
        """Test deeply nested JSON."""
        result = extract_json('{"a": {"b": {"c": {"d": {"e": 1}}}}}')
        assert result["a"]["b"]["c"]["d"]["e"] == 1

    def test_empty_object(self) -> None:
        """Test empty object."""
        result = extract_json("{}")
        assert result == {}

    def test_empty_array(self) -> None:
        """Test empty array."""
        result = extract_json("[]")
        assert result == []

    def test_json_with_newlines(self) -> None:
        """Test JSON with newlines (pretty-printed)."""
        text = """{
    "key": "value",
    "nested": {
        "inner": true
    }
}"""
        result = extract_json(text)
        assert result == {"key": "value", "nested": {"inner": True}}

    def test_multiple_json_in_markdown(self) -> None:
        """Test multiple JSON blocks in markdown."""
        text = """First:
```json
{"a": 1}
```

Second:
```json
{"b": 2}
```
"""
        result = extract_json(text, strategy="all")
        assert len(result) >= 2
