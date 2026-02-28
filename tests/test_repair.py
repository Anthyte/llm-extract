"""Tests for llm_extract.repair module."""

from llm_extract.repair import (
    _cleanup_whitespace,
    _complete_truncated,
    _fix_unquoted_keys,
    _is_json_string_quote,
    _normalize_quotes,
    _remove_trailing_commas,
    is_truncated_json,
    repair_json,
)


class TestRemoveTrailingCommas:
    """Tests for _remove_trailing_commas function."""

    def test_trailing_comma_in_object(self) -> None:
        """Test removing trailing comma in object."""
        text = '{"key": "value",}'
        result, repairs = _remove_trailing_commas(text)
        assert result == '{"key": "value"}'
        assert "trailing_comma_removal" in repairs

    def test_trailing_comma_in_array(self) -> None:
        """Test removing trailing comma in array."""
        text = "[1, 2, 3,]"
        result, repairs = _remove_trailing_commas(text)
        assert result == "[1, 2, 3]"
        assert "trailing_comma_removal" in repairs

    def test_multiple_trailing_commas(self) -> None:
        """Test removing multiple trailing commas."""
        text = '{"a": [1,], "b": 2,}'
        result, repairs = _remove_trailing_commas(text)
        assert result == '{"a": [1], "b": 2}'

    def test_trailing_comma_with_whitespace(self) -> None:
        """Test removing trailing comma with whitespace."""
        text = '{"key": "value" ,  }'
        result, repairs = _remove_trailing_commas(text)
        assert result == '{"key": "value"   }'

    def test_no_trailing_comma(self) -> None:
        """Test that valid JSON is unchanged."""
        text = '{"key": "value"}'
        result, repairs = _remove_trailing_commas(text)
        assert result == text
        assert repairs == []


class TestNormalizeQuotes:
    """Tests for _normalize_quotes function."""

    def test_single_quoted_keys(self) -> None:
        """Test converting single-quoted keys to double."""
        text = "{'key': 'value'}"
        result, repairs = _normalize_quotes(text)
        assert result == '{"key": "value"}'
        assert "quote_normalization" in repairs

    def test_mixed_quotes(self) -> None:
        """Test handling mixed quotes."""
        text = "{'key': \"value\"}"
        result, repairs = _normalize_quotes(text)
        assert result == '{"key": "value"}'

    def test_no_single_quotes(self) -> None:
        """Test that double-quoted JSON is unchanged."""
        text = '{"key": "value"}'
        result, repairs = _normalize_quotes(text)
        assert result == text
        assert repairs == []

    def test_escaped_quotes(self) -> None:
        """Test handling escaped quotes."""
        text = r'{"key": "value with \" quote"}'
        result, repairs = _normalize_quotes(text)
        assert result == text  # Should not modify escaped quotes

    def test_after_colon(self) -> None:
        """Test single quote after colon is normalized."""
        text = "{\"key\": 'value'}"
        result, repairs = _normalize_quotes(text)
        assert '"value"' in result

    def test_after_comma(self) -> None:
        """Test single quote after comma is normalized."""
        text = "{'a': 1, 'b': 2}"
        result, repairs = _normalize_quotes(text)
        assert '"a"' in result
        assert '"b"' in result

    def test_single_quote_not_json_context(self) -> None:
        """Test single quote not in JSON context is not normalized."""
        text = "some 'text' here"
        result, repairs = _normalize_quotes(text)
        assert result == text
        assert repairs == []


class TestIsJsonStringQuote:
    """Tests for _is_json_string_quote function."""

    def test_out_of_bounds(self) -> None:
        """Test position out of bounds."""
        assert _is_json_string_quote("test", 10) is False

    def test_after_opening_brace(self) -> None:
        """Test single quote after opening brace."""
        assert _is_json_string_quote("{'key'}", 1) is True

    def test_after_colon(self) -> None:
        """Test single quote after colon."""
        text = "{'key': 'value'}"
        assert _is_json_string_quote(text, 8) is True

    def test_before_closing_brace(self) -> None:
        """Test single quote before closing brace."""
        text = "{'key'}"
        assert _is_json_string_quote(text, 5) is True

    def test_not_json_context(self) -> None:
        """Test single quote not in JSON context."""
        assert _is_json_string_quote("it's a test", 2) is False

    def test_empty_before(self) -> None:
        """Test when nothing before the position."""
        assert _is_json_string_quote("'test", 0) is False


class TestFixUnquotedKeys:
    """Tests for _fix_unquoted_keys function."""

    def test_unquoted_key(self) -> None:
        """Test fixing unquoted key."""
        text = '{key: "value"}'
        result, repairs = _fix_unquoted_keys(text)
        assert result == '{"key": "value"}'
        assert "unquoted_key_fix" in repairs

    def test_multiple_unquoted_keys(self) -> None:
        """Test fixing multiple unquoted keys."""
        text = "{first: 1, second: 2}"
        result, repairs = _fix_unquoted_keys(text)
        assert '"first"' in result
        assert '"second"' in result

    def test_underscore_in_key(self) -> None:
        """Test fixing key with underscore."""
        text = '{my_key: "value"}'
        result, repairs = _fix_unquoted_keys(text)
        assert result == '{"my_key": "value"}'

    def test_already_quoted(self) -> None:
        """Test that quoted keys are unchanged."""
        text = '{"key": "value"}'
        result, repairs = _fix_unquoted_keys(text)
        assert result == text
        assert repairs == []

    def test_number_in_key(self) -> None:
        """Test fixing key with numbers."""
        text = '{key123: "value"}'
        result, repairs = _fix_unquoted_keys(text)
        assert result == '{"key123": "value"}'


class TestCleanupWhitespace:
    """Tests for _cleanup_whitespace function."""

    def test_remove_bom(self) -> None:
        """Test removing BOM."""
        text = '\ufeff{"key": "value"}'
        result, repairs = _cleanup_whitespace(text)
        assert result == '{"key": "value"}'
        assert "bom_removal" in repairs

    def test_remove_zero_width_space(self) -> None:
        """Test removing zero-width space."""
        text = '{"key"\u200b: "value"}'
        result, repairs = _cleanup_whitespace(text)
        assert "\u200b" not in result
        assert "invisible_char_removal" in repairs

    def test_no_special_chars(self) -> None:
        """Test that clean JSON is unchanged."""
        text = '{"key": "value"}'
        result, repairs = _cleanup_whitespace(text)
        assert result == text
        assert repairs == []


class TestIsTruncatedJson:
    """Tests for is_truncated_json function."""

    def test_complete_json(self) -> None:
        """Test that complete JSON is not truncated."""
        assert is_truncated_json('{"key": "value"}') is False
        assert is_truncated_json("[]") is False

    def test_unclosed_brace(self) -> None:
        """Test detection of unclosed brace."""
        assert is_truncated_json('{"key": "value"') is True
        assert is_truncated_json("{") is True

    def test_with_escaped_characters(self) -> None:
        """Test truncation detection with escaped characters."""
        # Complete JSON with escaped quote
        assert is_truncated_json(r'{"key": "value with \" quote"}') is False
        # Truncated JSON with escape
        assert is_truncated_json(r'{"key": "value\n') is True

    def test_escape_at_end(self) -> None:
        """Test JSON with escaped quote is complete."""
        # This has escaped quote and is complete
        assert is_truncated_json(r'{"key": "value\""}') is False

    def test_unclosed_bracket(self) -> None:
        """Test detection of unclosed bracket."""
        assert is_truncated_json("[1, 2, 3") is True
        assert is_truncated_json("[") is True

    def test_unclosed_string(self) -> None:
        """Test detection of unclosed string."""
        assert is_truncated_json('{"key": "value') is True

    def test_trailing_escape(self) -> None:
        """Test detection of trailing escape character."""
        assert is_truncated_json('{"key": "value\\') is True

    def test_trailing_escape_outside_string(self) -> None:
        """Test detection of trailing escape after closed string."""
        # Valid JSON followed by trailing backslash
        assert is_truncated_json('{"key": "value"}\\') is True

    def test_empty_input(self) -> None:
        """Test that empty input is not truncated."""
        assert is_truncated_json("") is False
        assert is_truncated_json("   ") is False

    def test_nested_structures(self) -> None:
        """Test truncation detection in nested structures."""
        assert is_truncated_json('{"a": {"b": 1}') is True
        assert is_truncated_json('{"a": [1, 2}') is True  # Mismatched


class TestCompleteTruncated:
    """Tests for _complete_truncated function."""

    def test_close_object(self) -> None:
        """Test closing unclosed object."""
        text = '{"key": "value"'
        result, repairs = _complete_truncated(text)
        assert result.endswith("}")
        assert "brace_completion" in repairs

    def test_close_array(self) -> None:
        """Test closing unclosed array."""
        text = "[1, 2, 3"
        result, repairs = _complete_truncated(text)
        assert result.endswith("]")

    def test_close_string(self) -> None:
        """Test closing unclosed string."""
        text = '{"key": "value'
        result, repairs = _complete_truncated(text)
        assert "string_completion" in repairs

    def test_with_escaped_chars(self) -> None:
        """Test completion with escaped characters."""
        text = r'{"key": "value\n'
        result, repairs = _complete_truncated(text)
        assert "string_completion" in repairs

    def test_with_escaped_quote(self) -> None:
        """Test completion preserves escaped quotes."""
        text = r'{"key": "value\"more'
        result, repairs = _complete_truncated(text)
        assert "string_completion" in repairs

    def test_close_nested(self) -> None:
        """Test closing nested structures."""
        text = '{"a": {"b": [1, 2'
        result, repairs = _complete_truncated(text)
        # Should close array, inner object, outer object
        assert result.count("]") >= 1
        assert result.count("}") >= 2

    def test_already_complete(self) -> None:
        """Test that complete JSON is unchanged."""
        text = '{"key": "value"}'
        result, repairs = _complete_truncated(text)
        assert result == text
        assert repairs == []


class TestRepairJson:
    """Tests for repair_json function."""

    def test_valid_json_unchanged(self) -> None:
        """Test that valid JSON is not modified."""
        text = '{"key": "value"}'
        result = repair_json(text)
        assert result.repaired == text
        assert result.repairs_applied == []
        assert result.is_truncated is False

    def test_trailing_comma_repair(self) -> None:
        """Test repair of trailing comma."""
        text = '{"key": "value",}'
        result = repair_json(text)
        assert result.repaired == '{"key": "value"}'
        assert "trailing_comma_removal" in result.repairs_applied

    def test_single_quote_repair(self) -> None:
        """Test repair of single quotes."""
        text = "{'key': 'value'}"
        result = repair_json(text)
        assert result.repaired == '{"key": "value"}'
        assert "quote_normalization" in result.repairs_applied

    def test_unquoted_key_repair(self) -> None:
        """Test repair of unquoted keys."""
        text = '{key: "value"}'
        result = repair_json(text)
        assert result.repaired == '{"key": "value"}'
        assert "unquoted_key_fix" in result.repairs_applied

    def test_combined_repairs(self) -> None:
        """Test multiple repairs combined."""
        text = "{key: 'value',}"
        result = repair_json(text)
        # Should fix unquoted key, single quotes, and trailing comma
        assert result.repaired == '{"key": "value"}'
        assert len(result.repairs_applied) >= 2

    def test_truncated_json_repair(self) -> None:
        """Test repair of truncated JSON."""
        text = '{"key": "value'
        result = repair_json(text)
        assert result.is_truncated is True
        # Should attempt to close string and brace
        assert "}" in result.repaired

    def test_max_iterations(self) -> None:
        """Test that max iterations is respected."""
        # This shouldn't cause infinite loop
        text = '{"key": "value"}'
        result = repair_json(text, max_iterations=1)
        assert result.repaired == text

    def test_bom_removal(self) -> None:
        """Test BOM removal."""
        text = '\ufeff{"key": "value"}'
        result = repair_json(text)
        assert result.repaired == '{"key": "value"}'
        assert "bom_removal" in result.repairs_applied
