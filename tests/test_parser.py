"""Tests for ai_extract.parser module."""

import json
from pathlib import Path

import pytest

from ai_extract import (
    ErrorType,
    ExtractError,
    ExtractionMethod,
    extract_json,
    extract_json_with_metadata,
)
from ai_extract.parser import _extract_first_valid

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SYNTHETIC_CASES = json.loads(
    (FIXTURE_DIR / "synthetic" / "test_cases.json").read_text(encoding="utf-8")
)["cases"]
REAL_CASES = json.loads((FIXTURE_DIR / "real" / "llm_outputs.json").read_text(encoding="utf-8"))[
    "cases"
]
ERROR_TYPE_BY_NAME = {
    "no_json_found": ErrorType.NO_JSON_FOUND,
    "invalid_json": ErrorType.INVALID_JSON,
    "ambiguous_multiple": ErrorType.AMBIGUOUS_MULTIPLE,
}
PAYLOADS = [
    ("object", '{"a": 1, "b": 2}', {"a": 1, "b": 2}),
    ("array", "[1, 2, 3]", [1, 2, 3]),
]
WRAPPERS = [
    ("plain", "{text}"),
    ("prefix", "prefix {text}"),
    ("suffix", "{text} suffix"),
    ("both", "prefix {text} suffix"),
    ("json_fence", "```json\n{text}\n```"),
    ("generic_fence", "```\n{text}\n```"),
    ("json_fence_text", "before\n```json\n{text}\n```\nafter"),
    ("generic_fence_text", "before\n```\n{text}\n```\nafter"),
]
COMBINATION_CASES: list[tuple[str, object, str]] = []
for payload_name, payload, expected in PAYLOADS:
    for wrapper_name, wrapper in WRAPPERS:
        COMBINATION_CASES.append(
            (
                wrapper.format(text=payload),
                expected,
                f"{payload_name}_{wrapper_name}",
            )
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

    def test_invalid_json_raises(self) -> None:
        """Test that malformed JSON raises error."""
        with pytest.raises(ExtractError) as exc_info:
            extract_json('{"key": "value",}')
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

    def test_strategy_all_skips_invalid(self) -> None:
        """Test 'all' strategy skips invalid JSON."""
        # First JSON is valid, second needs repair
        text = '{"a": 1} and {"b": 2,}'
        result = extract_json(text, strategy="all")
        # Should only get the valid one
        assert len(result) == 1
        assert {"a": 1} in result

    def test_strategy_all_all_fail(self) -> None:
        """Test 'all' strategy when all candidates fail."""
        # Malformed JSON that can't be repaired even with repair=True
        result = extract_json_with_metadata(
            "Here is some {broken: json} text",
            strategy="all",
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
        assert result.method == ExtractionMethod.DIRECT_PARSE
        assert result.error is None

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
        """Test invalid JSON error when parsing fails."""
        # Text that looks like JSON but can't be parsed
        result = extract_json_with_metadata('{"key": value_without_quotes}')
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.INVALID_JSON

    def test_extract_first_valid_empty(self) -> None:
        """Test empty candidates list returns invalid JSON error."""
        result = _extract_first_valid([])
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.INVALID_JSON
        assert result.error.message == "Failed to parse JSON from 0 candidate(s)"


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


class TestFixtureCases:
    """Tests for JSON extraction from fixture cases."""

    @pytest.mark.parametrize(
        ("case",),
        [(case,) for case in SYNTHETIC_CASES],
        ids=[case["name"] for case in SYNTHETIC_CASES],
    )
    def test_synthetic_cases(self, case: dict[str, object]) -> None:
        input_text = case["input"]
        if "expected_error" in case:
            expected_error = ERROR_TYPE_BY_NAME[case["expected_error"]]
            with pytest.raises(ExtractError) as exc_info:
                extract_json(input_text)
            assert exc_info.value.error_type == expected_error
            return
        if "expected" in case:
            assert extract_json(input_text) == case["expected"]
        if "expected_first" in case:
            assert extract_json(input_text, strategy="first") == case["expected_first"]
        if "expected_all" in case:
            assert extract_json(input_text, strategy="all") == case["expected_all"]

    @pytest.mark.parametrize(
        ("case",),
        [(case,) for case in REAL_CASES],
        ids=[case["name"] for case in REAL_CASES],
    )
    def test_real_cases(self, case: dict[str, object]) -> None:
        input_text = case["input"]
        if "expected" in case:
            assert extract_json(input_text) == case["expected"]
        if "expected_first" in case:
            assert extract_json(input_text, strategy="first") == case["expected_first"]
        if "expected_all" in case:
            assert extract_json(input_text, strategy="all") == case["expected_all"]
        if "expected_last" in case:
            result = extract_json(input_text, strategy="all")
            assert isinstance(result, list)
            assert result[-1] == case["expected_last"]


class TestCombinationCoverage:
    """Tests for wrapper and payload combinations."""

    @pytest.mark.parametrize(
        ("text", "expected", "case_id"),
        COMBINATION_CASES,
        ids=[case_id for _, _, case_id in COMBINATION_CASES],
    )
    def test_wrapped_payloads(self, text: str, expected: object, case_id: str) -> None:
        assert extract_json(text) == expected

    @pytest.mark.parametrize(
        ("first_payload", "second_payload"),
        [
            ('{"a": 1}', '{"b": 2}'),
            ('{"a": 1}', "[1, 2]"),
            ("[1, 2]", '{"b": 2}'),
        ],
    )
    def test_multi_block_combinations(self, first_payload: str, second_payload: str) -> None:
        text = f"{first_payload} and then {second_payload}"
        result = extract_json(text, strategy="all")
        assert len(result) == 2
