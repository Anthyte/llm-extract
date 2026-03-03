"""Tests for ai_extract.json_core internals."""

import pytest

from ai_extract import ErrorType, ExtractError
from ai_extract.json_core import (
    _collect_subtree_all,
    _extract_first_streaming,
    _extract_json_with_metadata,
    _find_by_braces,
    _find_candidates,
    _parse_all,
    _parse_subtree_first,
    _try_direct_parse_candidate,
    extract_json,
)
from ai_extract.types import Candidate, ExtractionMethod


class TestTryDirectParseCandidate:
    def test_valid_json_returns_candidate(self) -> None:
        candidate = _try_direct_parse_candidate('{"k": 1}')
        assert candidate is not None
        assert candidate.method == ExtractionMethod.DIRECT_PARSE
        assert candidate.parsed_data == {"k": 1}

    def test_invalid_json_returns_none(self) -> None:
        assert _try_direct_parse_candidate("not json") is None


class TestParseSubtreeFirst:
    def test_returns_cached_data(self) -> None:
        candidate = Candidate("{}", ExtractionMethod.BRACE_MATCH, 0, 2, parsed_data={"x": 1})
        assert _parse_subtree_first(candidate) == {"x": 1}

    def test_falls_back_to_child_on_parent_failure(self) -> None:
        child = Candidate('{"b": 1}', ExtractionMethod.BRACE_MATCH, 7, 15)
        parent = Candidate('{"a": {"b": 1}', ExtractionMethod.BRACE_MATCH, 0, 15)
        parent.children = [child]
        assert _parse_subtree_first(parent) == {"b": 1}

    def test_returns_none_when_nothing_valid(self) -> None:
        candidate = Candidate("{invalid}", ExtractionMethod.BRACE_MATCH, 0, 9)
        assert _parse_subtree_first(candidate) is None

    def test_skips_invalid_child_and_uses_next_child(self) -> None:
        bad_child = Candidate("{broken}", ExtractionMethod.BRACE_MATCH, 2, 10)
        good_child = Candidate('{"ok": 1}', ExtractionMethod.BRACE_MATCH, 11, 20)
        parent = Candidate("{...}", ExtractionMethod.BRACE_MATCH, 0, 20)
        parent.children = [good_child, bad_child]
        assert _parse_subtree_first(parent) == {"ok": 1}


class TestExtractFirstStreaming:
    def test_returns_first_top_level_json(self) -> None:
        result = _extract_first_streaming('{"a": 1} and {"b": 2}')
        assert result.success is True
        assert result.data == {"a": 1}

    def test_uses_unfinished_region_fallback(self) -> None:
        result = _extract_first_streaming('{"a": {"b": 1}')
        assert result.success is True
        assert result.data == {"b": 1}

    def test_returns_error_when_no_json(self) -> None:
        result = _extract_first_streaming("hello world")
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.NO_JSON_FOUND

    def test_handles_escaped_quotes_in_string(self) -> None:
        text = 'prefix {"k":"a\\\\\\"b"} suffix'
        result = _extract_first_streaming(text)
        assert result.success is True
        assert result.data == {"k": 'a\\"b'}

    def test_ignores_stray_closer_and_mismatch(self) -> None:
        assert _extract_first_streaming('} {"a": 1}').data == {"a": 1}
        bad = _extract_first_streaming("{]")
        assert bad.success is False

    def test_fallback_skips_invalid_then_returns_valid(self) -> None:
        # Unclosed outer object leaves two region candidates at EOF:
        # first invalid ({broken}), second valid ({"ok":1}).
        text = '{{broken}{"ok":1}'
        result = _extract_first_streaming(text)
        assert result.success is True
        assert result.data == {"ok": 1}

    def test_sibling_nested_candidates_hit_non_subset_break(self) -> None:
        # Two sibling objects inside one top-level array force the while-loop
        # break branch in nested candidate compaction.
        result = _extract_first_streaming('[{"a":1},{"b":2}]')
        assert result.success is True
        assert result.data == [{"a": 1}, {"b": 2}]


class TestFindByBraces:
    def test_simple_object(self) -> None:
        candidates = _find_by_braces("{}")
        assert len(candidates) == 1
        assert candidates[0].raw == "{}"
        assert candidates[0].start_pos == 0
        assert candidates[0].end_pos == 2

    def test_simple_array(self) -> None:
        candidates = _find_by_braces("[]")
        assert len(candidates) == 1
        assert candidates[0].raw == "[]"

    def test_nested_object_tree(self) -> None:
        candidates = _find_by_braces('{"a": {"b": 1}}')
        assert len(candidates) == 1
        assert candidates[0].raw == '{"a": {"b": 1}}'
        assert len(candidates[0].children) == 1
        assert candidates[0].children[0].raw == '{"b": 1}'

    def test_string_and_escape_handling(self) -> None:
        text = r'{"key": "value with { brace and \" quote"}'
        candidates = _find_by_braces(text)
        assert len(candidates) == 1
        assert candidates[0].raw == text

    def test_unbalanced_and_mismatched(self) -> None:
        assert _find_by_braces("{") == []
        assert _find_by_braces("{]") == []
        assert _find_by_braces("[}") == []
        assert _find_by_braces("]{}")[0].raw == "{}"

    def test_multiple_top_level_candidates(self) -> None:
        candidates = _find_by_braces("prefix {} middle [] suffix")
        assert [c.raw for c in candidates] == ["{}", "[]"]


class TestFindCandidates:
    def test_prefers_direct_parse(self) -> None:
        candidates = _find_candidates('{"a": 1}')
        assert len(candidates) == 1
        assert candidates[0].method == ExtractionMethod.DIRECT_PARSE
        assert candidates[0].parsed_data == {"a": 1}

    def test_falls_back_to_brace_scan(self) -> None:
        candidates = _find_candidates('before {"a": 1} after')
        assert len(candidates) == 1
        assert candidates[0].method == ExtractionMethod.BRACE_MATCH


class TestCollectSubtreeAll:
    def test_collects_parent_and_skips_children_when_parent_valid(self) -> None:
        parent = Candidate('{"a": 1}', ExtractionMethod.BRACE_MATCH, 0, 8)
        parent.children = [Candidate('{"b": 2}', ExtractionMethod.BRACE_MATCH, 2, 10)]
        out: list[object] = []
        _collect_subtree_all(parent, out)
        assert out == [{"a": 1}]

    def test_collects_child_when_parent_invalid(self) -> None:
        parent = Candidate('{"a": {"b": 1}', ExtractionMethod.BRACE_MATCH, 0, 15)
        parent.children = [Candidate('{"b": 1}', ExtractionMethod.BRACE_MATCH, 7, 15)]
        out: list[object] = []
        _collect_subtree_all(parent, out)
        assert out == [{"b": 1}]

    def test_uses_cached_parent_data(self) -> None:
        parent = Candidate("{}", ExtractionMethod.BRACE_MATCH, 0, 2, parsed_data={"cached": True})
        out: list[object] = []
        _collect_subtree_all(parent, out)
        assert out == [{"cached": True}]


class TestParseAll:
    def test_returns_success_with_results(self) -> None:
        candidates = _find_candidates('{"a": 1} and {"b": 2}')
        result = _parse_all(candidates)
        assert result.success is True
        assert result.data == [{"a": 1}, {"b": 2}]

    def test_returns_error_when_all_fail(self) -> None:
        candidates = _find_candidates("{broken: json}")
        result = _parse_all(candidates)
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.NO_JSON_FOUND


class TestExtractJsonWithMetadataInternal:
    def test_successful_extraction(self) -> None:
        result = _extract_json_with_metadata('{"key": "value"}')
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_all_strategy_returns_all_parsed_values(self) -> None:
        first_result = _extract_json_with_metadata('{"a": 1} and {"b": 2}')
        assert first_result.success is True
        assert first_result.data == {"a": 1}

        all_result = _extract_json_with_metadata('{"a": 1} and {"b": 2}', strategy="all")
        assert all_result.success is True
        assert all_result.data == [{"a": 1}, {"b": 2}]

    def test_empty_input(self) -> None:
        result = _extract_json_with_metadata("")
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.NO_JSON_FOUND

    def test_invalid_strategy_raises(self) -> None:
        with pytest.raises(ValueError):
            _extract_json_with_metadata("{}", strategy="bad")  # type: ignore[arg-type]

    def test_all_strategy_no_candidates_error(self) -> None:
        result = _extract_json_with_metadata("plain text only", strategy="all")
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ErrorType.NO_JSON_FOUND


class TestExtractJsonPublic:
    def test_success(self) -> None:
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_all_strategy(self) -> None:
        assert extract_json('{"a": 1} and {"b": 2}', strategy="all") == [{"a": 1}, {"b": 2}]

    def test_raise_on_error_false_returns_none(self) -> None:
        assert extract_json("no json", raise_on_error=False) is None

    def test_raise_on_error_true_raises(self) -> None:
        with pytest.raises(ExtractError):
            extract_json("no json", raise_on_error=True)
