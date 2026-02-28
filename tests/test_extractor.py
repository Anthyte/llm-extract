"""Tests for llm_extract.extractor module."""

from llm_extract.extractor import (
    _calculate_brace_match_confidence,
    _looks_like_json,
    _match_braces,
    extract_all_candidates,
    extract_direct,
    extract_from_brace_matching,
    extract_from_markdown_fence,
    extract_heuristic,
    rank_candidates,
)
from llm_extract.types import Candidate, ExtractionMethod


class TestLooksLikeJson:
    """Tests for _looks_like_json helper."""

    def test_valid_object(self) -> None:
        """Test that valid JSON objects are recognized."""
        assert _looks_like_json('{"key": "value"}') is True
        assert _looks_like_json("{}") is True
        assert _looks_like_json('  {"key": 1}  ') is True

    def test_valid_array(self) -> None:
        """Test that valid JSON arrays are recognized."""
        assert _looks_like_json("[1, 2, 3]") is True
        assert _looks_like_json("[]") is True
        assert _looks_like_json('  [{"a": 1}]  ') is True

    def test_invalid_json(self) -> None:
        """Test that invalid JSON is rejected."""
        assert _looks_like_json("") is False
        assert _looks_like_json("   ") is False
        assert _looks_like_json("hello") is False
        assert _looks_like_json("{incomplete") is False
        assert _looks_like_json("not json}") is False


class TestMatchBraces:
    """Tests for _match_braces helper."""

    def test_simple_object(self) -> None:
        """Test matching simple objects."""
        result = _match_braces("{}", 0)
        assert result == (0, 1)

    def test_simple_array(self) -> None:
        """Test matching simple arrays."""
        result = _match_braces("[]", 0)
        assert result == (0, 1)

    def test_nested_object(self) -> None:
        """Test matching nested objects."""
        text = '{"a": {"b": 1}}'
        result = _match_braces(text, 0)
        assert result == (0, len(text) - 1)

    def test_object_with_string(self) -> None:
        """Test that braces in strings are ignored."""
        text = '{"key": "value with { brace"}'
        result = _match_braces(text, 0)
        assert result == (0, len(text) - 1)

    def test_escaped_quotes(self) -> None:
        """Test handling of escaped quotes."""
        text = r'{"key": "value with \" quote"}'
        result = _match_braces(text, 0)
        assert result == (0, len(text) - 1)

    def test_mixed_brackets(self) -> None:
        """Test mixed braces and brackets."""
        text = '{"arr": [1, 2, {"nested": true}]}'
        result = _match_braces(text, 0)
        assert result == (0, len(text) - 1)

    def test_unbalanced_braces(self) -> None:
        """Test that unbalanced braces return None."""
        assert _match_braces("{", 0) is None
        assert _match_braces("{{}", 0) is None

    def test_mismatched_braces(self) -> None:
        """Test that mismatched braces return None."""
        assert _match_braces("{]", 0) is None
        assert _match_braces("[}", 0) is None

    def test_start_not_brace(self) -> None:
        """Test that non-brace start returns None."""
        assert _match_braces("abc", 0) is None
        assert _match_braces('{"a": 1}', 1) is None

    def test_out_of_bounds(self) -> None:
        """Test that out of bounds start returns None."""
        assert _match_braces("{}", 10) is None

    def test_offset_start(self) -> None:
        """Test matching with offset start position."""
        text = "prefix {}"
        result = _match_braces(text, 7)
        assert result == (7, 8)


class TestCalculateBraceMatchConfidence:
    """Tests for _calculate_brace_match_confidence helper."""

    def test_base_confidence(self) -> None:
        """Test base confidence for simple JSON."""
        conf = _calculate_brace_match_confidence("{}")
        # Short content gets penalty, no quotes or colons
        assert 0.5 <= conf <= 0.8

    def test_with_quotes(self) -> None:
        """Test confidence bonus for having quotes."""
        conf_with = _calculate_brace_match_confidence('{"key"}')
        conf_without = _calculate_brace_match_confidence("{key}")
        assert conf_with > conf_without

    def test_with_colons(self) -> None:
        """Test confidence bonus for having colons."""
        conf_with = _calculate_brace_match_confidence('{"key": 1}')
        conf_without = _calculate_brace_match_confidence('{"key" 1}')
        assert conf_with > conf_without

    def test_short_content_penalty(self) -> None:
        """Test that very short content gets penalized."""
        conf_short = _calculate_brace_match_confidence("{}")
        conf_longer = _calculate_brace_match_confidence(
            '{"key": "value", "another": 123}'
        )
        assert conf_longer > conf_short

    def test_max_confidence_capped(self) -> None:
        """Test that confidence is capped at 0.9."""
        # Even with all bonuses, should not exceed 0.9
        conf = _calculate_brace_match_confidence('{"key": "value", "a": "b"}')
        assert conf <= 0.9


class TestExtractDirect:
    """Tests for extract_direct function."""

    def test_pure_json_object(self) -> None:
        """Test extracting pure JSON object."""
        candidates = extract_direct('{"key": "value"}')
        assert len(candidates) == 1
        assert candidates[0].raw == '{"key": "value"}'
        assert candidates[0].method == ExtractionMethod.DIRECT_PARSE
        assert candidates[0].confidence == 1.0

    def test_pure_json_array(self) -> None:
        """Test extracting pure JSON array."""
        candidates = extract_direct("[1, 2, 3]")
        assert len(candidates) == 1
        assert candidates[0].raw == "[1, 2, 3]"

    def test_with_whitespace(self) -> None:
        """Test that surrounding whitespace is handled."""
        candidates = extract_direct('  {"key": 1}  ')
        assert len(candidates) == 1
        assert candidates[0].raw == '{"key": 1}'

    def test_non_json(self) -> None:
        """Test that non-JSON returns empty list."""
        assert extract_direct("hello world") == []
        assert extract_direct("") == []
        assert extract_direct("   ") == []

    def test_partial_json(self) -> None:
        """Test that partial JSON doesn't match."""
        assert extract_direct("Here is JSON: {}") == []


class TestExtractFromMarkdownFence:
    """Tests for extract_from_markdown_fence function."""

    def test_json_fence(self) -> None:
        """Test extracting from ```json fence."""
        text = """Here is the output:
```json
{"key": "value"}
```
"""
        candidates = extract_from_markdown_fence(text)
        assert len(candidates) == 1
        assert candidates[0].raw == '{"key": "value"}'
        assert candidates[0].method == ExtractionMethod.MARKDOWN_FENCE
        assert candidates[0].confidence == 0.95

    def test_generic_fence(self) -> None:
        """Test extracting from generic ``` fence."""
        text = """Output:
```
{"key": "value"}
```
"""
        candidates = extract_from_markdown_fence(text)
        assert len(candidates) == 1
        assert candidates[0].raw == '{"key": "value"}'
        assert candidates[0].confidence == 0.85

    def test_multiple_fences(self) -> None:
        """Test extracting from multiple fences."""
        text = """First:
```json
{"a": 1}
```
Second:
```json
{"b": 2}
```
"""
        candidates = extract_from_markdown_fence(text)
        assert len(candidates) == 2

    def test_case_insensitive(self) -> None:
        """Test that JSON fence is case insensitive."""
        text = """```JSON
{"key": "value"}
```"""
        candidates = extract_from_markdown_fence(text)
        assert len(candidates) == 1

    def test_non_json_content_ignored(self) -> None:
        """Test that non-JSON content in fences is ignored."""
        text = """```json
not json content
```"""
        candidates = extract_from_markdown_fence(text)
        assert len(candidates) == 0

    def test_no_fences(self) -> None:
        """Test that text without fences returns empty list."""
        assert extract_from_markdown_fence('{"key": "value"}') == []


class TestExtractFromBraceMatching:
    """Tests for extract_from_brace_matching function."""

    def test_simple_object(self) -> None:
        """Test extracting simple JSON object."""
        candidates = extract_from_brace_matching('Here is JSON: {"key": "value"}')
        assert len(candidates) == 1
        assert candidates[0].raw == '{"key": "value"}'
        assert candidates[0].method == ExtractionMethod.BRACE_MATCH

    def test_multiple_objects(self) -> None:
        """Test extracting multiple JSON objects."""
        text = '{"a": 1} and {"b": 2}'
        candidates = extract_from_brace_matching(text)
        assert len(candidates) == 2

    def test_nested_objects(self) -> None:
        """Test that nested objects are handled correctly."""
        text = '{"outer": {"inner": 1}}'
        candidates = extract_from_brace_matching(text)
        # Should return the outermost object
        assert len(candidates) == 1
        assert candidates[0].raw == '{"outer": {"inner": 1}}'

    def test_array(self) -> None:
        """Test extracting JSON array."""
        candidates = extract_from_brace_matching("Data: [1, 2, 3]")
        assert len(candidates) == 1
        assert candidates[0].raw == "[1, 2, 3]"

    def test_no_json(self) -> None:
        """Test that text without JSON returns empty list."""
        assert extract_from_brace_matching("no json here") == []


class TestExtractHeuristic:
    """Tests for extract_heuristic function."""

    def test_here_is_json_pattern(self) -> None:
        """Test 'here is the JSON:' pattern."""
        text = 'Here is the JSON: {"key": "value"}'
        candidates = extract_heuristic(text)
        assert len(candidates) == 1
        assert candidates[0].raw == '{"key": "value"}'
        assert candidates[0].method == ExtractionMethod.HEURISTIC
        assert candidates[0].confidence == 0.6

    def test_heres_pattern(self) -> None:
        """Test "here's the output:" pattern."""
        text = 'Here\'s the output: {"a": 1}'
        candidates = extract_heuristic(text)
        assert len(candidates) >= 1
        assert candidates[0].raw == '{"a": 1}'

    def test_result_pattern(self) -> None:
        """Test 'result:' pattern."""
        text = 'Result: {"data": true}'
        candidates = extract_heuristic(text)
        assert len(candidates) == 1

    def test_no_pattern_match(self) -> None:
        """Test that text without patterns returns empty list."""
        assert extract_heuristic('{"key": "value"}') == []


class TestExtractAllCandidates:
    """Tests for extract_all_candidates function."""

    def test_combines_strategies(self) -> None:
        """Test that all strategies are combined."""
        text = """Here is the result:
```json
{"fenced": true}
```
Also: {"inline": true}
"""
        candidates = extract_all_candidates(text)
        # Should find fenced and inline
        assert len(candidates) >= 2

    def test_sorted_by_confidence(self) -> None:
        """Test that candidates are sorted by confidence."""
        text = """```json
{"high": true}
```
{"medium": true}"""
        candidates = extract_all_candidates(text)
        # Should be sorted high to low confidence
        for i in range(len(candidates) - 1):
            assert candidates[i].confidence >= candidates[i + 1].confidence

    def test_deduplication(self) -> None:
        """Test that duplicate candidates are removed."""
        # Direct parse might match the same as brace matching
        text = '{"key": "value"}'
        candidates = extract_all_candidates(text)
        # Should only have one candidate despite multiple strategies finding it
        raws = [c.raw for c in candidates]
        assert len(raws) == len(set(raws))

    def test_empty_input(self) -> None:
        """Test that empty input returns empty list."""
        assert extract_all_candidates("") == []
        assert extract_all_candidates("no json here") == []


class TestRankCandidates:
    """Tests for rank_candidates function."""

    def test_empty_list(self) -> None:
        """Test ranking empty list."""
        assert rank_candidates([]) == []

    def test_single_candidate(self) -> None:
        """Test ranking single candidate."""
        candidate = Candidate(
            raw="{}",
            start_pos=0,
            end_pos=2,
            method=ExtractionMethod.BRACE_MATCH,
            confidence=0.8,
        )
        result = rank_candidates([candidate])
        assert len(result) == 1
        assert result[0] == candidate

    def test_prefers_direct_parse(self) -> None:
        """Test that DIRECT_PARSE gets bonus."""
        direct = Candidate(
            raw="{}",
            start_pos=0,
            end_pos=2,
            method=ExtractionMethod.DIRECT_PARSE,
            confidence=0.8,
        )
        brace = Candidate(
            raw="{}",
            start_pos=0,
            end_pos=2,
            method=ExtractionMethod.BRACE_MATCH,
            confidence=0.8,
        )
        result = rank_candidates([brace, direct])
        assert result[0].method == ExtractionMethod.DIRECT_PARSE

    def test_prefers_larger(self) -> None:
        """Test that larger structures get bonus."""
        small = Candidate(
            raw="{}",
            start_pos=0,
            end_pos=2,
            method=ExtractionMethod.BRACE_MATCH,
            confidence=0.8,
        )
        large = Candidate(
            raw='{"key": "value", "another": "data"}',
            start_pos=0,
            end_pos=35,
            method=ExtractionMethod.BRACE_MATCH,
            confidence=0.8,
        )
        result = rank_candidates([small, large])
        assert len(result[0].raw) > len(result[1].raw)
