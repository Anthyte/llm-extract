"""JSON extraction strategies for detecting JSON in messy text."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .types import Candidate, ExtractionMethod

if TYPE_CHECKING:
    pass

# Precompiled regex patterns for performance
_MARKDOWN_FENCE_JSON = re.compile(
    r"```json\s*\n([\s\S]*?)\n\s*```",
    re.IGNORECASE,
)
_MARKDOWN_FENCE_GENERIC = re.compile(
    r"```\s*\n([\s\S]*?)\n\s*```",
)
_MARKDOWN_FENCE_ANY = re.compile(
    r"```(?:\w+)?\s*\n([\s\S]*?)\n\s*```",
)


def extract_from_markdown_fence(text: str) -> list[Candidate]:
    """Extract JSON candidates from markdown code fences.

    Tries multiple patterns:
    1. ```json ... ``` (highest confidence)
    2. ``` ... ``` (generic fence, lower confidence)
    """
    candidates: list[Candidate] = []

    # Try JSON-specific fences first (highest confidence)
    for match in _MARKDOWN_FENCE_JSON.finditer(text):
        content = match.group(1).strip()
        if content and _looks_like_json(content):
            candidates.append(
                Candidate(
                    raw=content,
                    start_pos=match.start(1),
                    end_pos=match.end(1),
                    method=ExtractionMethod.MARKDOWN_FENCE,
                    confidence=0.95,
                )
            )

    # Try generic fences (lower confidence)
    for match in _MARKDOWN_FENCE_ANY.finditer(text):
        content = match.group(1).strip()
        if content and _looks_like_json(content):
            # Check if this candidate overlaps with an existing one
            is_duplicate = any(
                c.start_pos <= match.start(1) <= c.end_pos
                or c.start_pos <= match.end(1) <= c.end_pos
                for c in candidates
            )
            if not is_duplicate:
                candidates.append(
                    Candidate(
                        raw=content,
                        start_pos=match.start(1),
                        end_pos=match.end(1),
                        method=ExtractionMethod.MARKDOWN_FENCE,
                        confidence=0.85,
                    )
                )

    return candidates


def extract_from_brace_matching(text: str) -> list[Candidate]:
    """Extract JSON candidates using brace matching algorithm.

    Finds balanced {...} and [...] structures in the text.
    """
    candidates: list[Candidate] = []

    # Find all potential JSON start positions
    i = 0
    while i < len(text):
        if text[i] in "{[":
            result = _match_braces(text, i)
            if result is not None:
                start, end = result
                raw = text[start : end + 1]
                # Calculate confidence based on structure
                confidence = _calculate_brace_match_confidence(raw)
                candidates.append(
                    Candidate(
                        raw=raw,
                        start_pos=start,
                        end_pos=end + 1,
                        method=ExtractionMethod.BRACE_MATCH,
                        confidence=confidence,
                    )
                )
                # Move past this match to avoid nested duplicates
                i = end + 1
                continue
        i += 1

    return candidates


def _match_braces(text: str, start: int) -> tuple[int, int] | None:
    """Match balanced braces starting at position start.

    Returns (start, end) positions if balanced, None otherwise.
    Handles strings and escaped characters properly.
    """
    if start >= len(text) or text[start] not in "{[":
        return None

    opener = text[start]
    stack = [opener]
    i = start + 1
    in_string = False
    escape_next = False

    while i < len(text) and stack:
        char = text[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if char == "\\":
            escape_next = True
            i += 1
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            i += 1
            continue

        if in_string:
            i += 1
            continue

        if char in "{[":
            stack.append(char)
        elif char == "}":
            if stack and stack[-1] == "{":
                stack.pop()
            else:
                # Mismatched braces
                return None
        elif char == "]":
            if stack and stack[-1] == "[":
                stack.pop()
            else:
                # Mismatched brackets
                return None

        i += 1

    if not stack:
        return (start, i - 1)
    return None


def _calculate_brace_match_confidence(raw: str) -> float:
    """Calculate confidence score for a brace-matched candidate."""
    base_confidence = 0.8

    # Bonus for having typical JSON structure
    if '"' in raw:
        base_confidence += 0.05

    # Bonus for having colons (key-value pairs)
    if ":" in raw:
        base_confidence += 0.05

    # Penalty for very short content
    if len(raw) < 10:
        base_confidence -= 0.1

    # Cap at 0.9 (markdown fence is more reliable)
    return min(0.9, max(0.5, base_confidence))


def extract_direct(text: str) -> list[Candidate]:
    """Try to extract the entire text as JSON (after stripping whitespace)."""
    stripped = text.strip()

    if not stripped:
        return []

    if _looks_like_json(stripped):
        return [
            Candidate(
                raw=stripped,
                start_pos=0,
                end_pos=len(text),
                method=ExtractionMethod.DIRECT_PARSE,
                confidence=1.0,
            )
        ]

    return []


def extract_heuristic(text: str) -> list[Candidate]:
    """Extract JSON using heuristic patterns.

    Looks for common patterns like "Here's the JSON:" followed by JSON.
    This is a fallback strategy with lower confidence.
    """
    candidates: list[Candidate] = []

    # Patterns that often precede JSON
    patterns = [
        r"(?:here(?:'s| is)(?: the)? (?:json|output|result|response)):?\s*",
        r"(?:json (?:output|response|result)):?\s*",
        r"(?:output|result|response):?\s*",
    ]

    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        for match in regex.finditer(text):
            # Look for JSON after this pattern
            after_match = text[match.end() :]
            brace_candidates = extract_from_brace_matching(after_match)
            for bc in brace_candidates:
                # Adjust positions relative to original text
                candidates.append(
                    Candidate(
                        raw=bc.raw,
                        start_pos=match.end() + bc.start_pos,
                        end_pos=match.end() + bc.end_pos,
                        method=ExtractionMethod.HEURISTIC,
                        confidence=0.6,  # Lower confidence for heuristic
                    )
                )
                break  # Only take first match after each pattern

    return candidates


def _looks_like_json(text: str) -> bool:
    """Quick check if text looks like it could be JSON."""
    stripped = text.strip()
    if not stripped:
        return False

    # Must start with { or [
    if stripped[0] not in "{[":
        return False

    # Must end with } or ]
    return stripped[-1] in "}}]"


def extract_all_candidates(text: str) -> list[Candidate]:
    """Extract all JSON candidates from text using all strategies.

    Returns candidates sorted by confidence (highest first).
    """
    candidates: list[Candidate] = []

    # Strategy 1: Direct parse (highest confidence if entire text is JSON)
    candidates.extend(extract_direct(text))

    # Strategy 2: Markdown fences (high confidence)
    candidates.extend(extract_from_markdown_fence(text))

    # Strategy 3: Brace matching (medium confidence)
    candidates.extend(extract_from_brace_matching(text))

    # Strategy 4: Heuristic (low confidence)
    candidates.extend(extract_heuristic(text))

    # Remove duplicates based on raw content
    seen_raw: set[str] = set()
    unique_candidates: list[Candidate] = []
    for c in candidates:
        if c.raw not in seen_raw:
            seen_raw.add(c.raw)
            unique_candidates.append(c)

    # Sort by confidence (highest first)
    unique_candidates.sort(key=lambda c: c.confidence, reverse=True)

    return unique_candidates


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Rank candidates by confidence and other factors.

    Returns a new list sorted by ranking score.
    """
    if not candidates:
        return []

    def ranking_score(c: Candidate) -> float:
        score = c.confidence

        # Bonus for larger structures (more likely to be the intended JSON)
        length_bonus = min(0.1, len(c.raw) / 10000)
        score += length_bonus

        # Bonus for DIRECT_PARSE method
        if c.method == ExtractionMethod.DIRECT_PARSE:
            score += 0.1

        return score

    return sorted(candidates, key=ranking_score, reverse=True)
