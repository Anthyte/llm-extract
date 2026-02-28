"""JSON repair strategies for fixing malformed JSON."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RepairResult:
    """Result of a repair attempt."""

    repaired: str
    repairs_applied: list[str] = field(default_factory=list)
    is_truncated: bool = False


def repair_json(text: str, max_iterations: int = 5) -> RepairResult:
    """Apply all safe repair strategies to fix malformed JSON.

    Args:
        text: The JSON string to repair.
        max_iterations: Maximum number of repair iterations.

    Returns:
        RepairResult with repaired string and list of repairs applied.
    """
    repairs_applied: list[str] = []
    current = text
    is_truncated = False

    for _ in range(max_iterations):
        previous = current

        # Apply repairs in order of safety
        current, applied = _remove_trailing_commas(current)
        repairs_applied.extend(applied)

        current, applied = _normalize_quotes(current)
        repairs_applied.extend(applied)

        current, applied = _fix_unquoted_keys(current)
        repairs_applied.extend(applied)

        current, applied = _cleanup_whitespace(current)
        repairs_applied.extend(applied)

        # If no changes were made, we're done
        if current == previous:
            break

    # Check for truncation and attempt completion
    if is_truncated_json(current):
        is_truncated = True
        current, applied = _complete_truncated(current)
        repairs_applied.extend(applied)

    return RepairResult(
        repaired=current,
        repairs_applied=repairs_applied,
        is_truncated=is_truncated,
    )


def _remove_trailing_commas(text: str) -> tuple[str, list[str]]:
    """Remove trailing commas before } or ].

    Example: {"a": 1,} -> {"a": 1}
    """
    repairs: list[str] = []

    # Pattern: comma followed by optional whitespace and closing brace/bracket
    pattern = re.compile(r",(\s*[}\]])")
    new_text = pattern.sub(r"\1", text)

    if new_text != text:
        repairs.append("trailing_comma_removal")

    return new_text, repairs


def _normalize_quotes(text: str) -> tuple[str, list[str]]:
    """Convert single quotes to double quotes for JSON compliance.

    This is tricky - we need to handle:
    - Keys: 'key' -> "key"
    - String values: 'value' -> "value"
    - Escaped quotes within strings
    - Don't change apostrophes in actual string content
    """
    repairs: list[str] = []

    # Simple approach: replace single quotes that look like JSON string delimiters
    # This pattern looks for single quotes around keys or simple values
    result: list[str] = []
    i = 0
    in_double_string = False
    modified = False

    while i < len(text):
        char = text[i]

        # Handle escape sequences
        if char == "\\" and i + 1 < len(text):
            result.append(char)
            result.append(text[i + 1])
            i += 2
            continue

        # Track if we're in a double-quoted string
        if char == '"':
            in_double_string = not in_double_string
            result.append(char)
            i += 1
            continue

        # Replace single quotes with double quotes when not in a string
        if char == "'" and not in_double_string and _is_json_string_quote(text, i):
            result.append('"')
            modified = True
            i += 1
            continue

        result.append(char)
        i += 1

    if modified:
        repairs.append("quote_normalization")

    return "".join(result), repairs


def _is_json_string_quote(text: str, pos: int) -> bool:
    """Check if a single quote at position pos is likely a JSON string delimiter."""
    if pos >= len(text):
        return False

    # Look at context before and after
    before = text[:pos].rstrip()
    after = text[pos + 1 :]

    # After { or [ or : or , -> likely start of key/value
    if before and before[-1] in "{[:,":
        return True

    # Before } or ] or : or , -> likely end of key/value
    # Look for the next non-whitespace character
    after_stripped = after.lstrip()
    return bool(after_stripped and after_stripped[0] in "}]:,")


def _fix_unquoted_keys(text: str) -> tuple[str, list[str]]:
    """Fix unquoted keys in JSON objects.

    Example: {key: "value"} -> {"key": "value"}
    """
    repairs: list[str] = []

    # Pattern: unquoted identifier followed by colon
    # Must be after { or ,
    pattern = re.compile(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)")

    def replace_key(match: re.Match[str]) -> str:
        return f'{match.group(1)}"{match.group(2)}"{match.group(3)}'

    new_text = pattern.sub(replace_key, text)

    if new_text != text:
        repairs.append("unquoted_key_fix")

    return new_text, repairs


def _cleanup_whitespace(text: str) -> tuple[str, list[str]]:
    """Clean up problematic whitespace in JSON.

    - Remove BOM (Byte Order Mark)
    - Remove other invisible Unicode characters
    """
    repairs: list[str] = []

    # Remove BOM
    if text.startswith("\ufeff"):
        text = text[1:]
        repairs.append("bom_removal")

    # Remove zero-width characters
    zero_width_chars = [
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\ufeff",  # BOM (also zero-width no-break space)
    ]

    original = text
    for char in zero_width_chars:
        text = text.replace(char, "")

    if text != original and "bom_removal" not in repairs:
        repairs.append("invisible_char_removal")

    return text, repairs


def is_truncated_json(text: str) -> bool:
    """Detect if JSON appears to be truncated.

    Checks for:
    - Unclosed braces/brackets
    - Unclosed strings
    - Incomplete escape sequences
    """
    stripped = text.strip()
    if not stripped:
        return False

    # Count braces and brackets
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False

    for char in stripped:
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            open_braces += 1
        elif char == "}":
            open_braces -= 1
        elif char == "[":
            open_brackets += 1
        elif char == "]":
            open_brackets -= 1

    # Check for unclosed strings (odd number of unescaped quotes)
    if in_string:
        return True

    # Check for unclosed braces/brackets
    if open_braces > 0 or open_brackets > 0:
        return True

    # Check for trailing escape character
    return bool(escape_next)


def _complete_truncated(text: str) -> tuple[str, list[str]]:
    """Attempt to complete truncated JSON by closing open structures.

    This is a best-effort repair that may not produce valid JSON,
    but gives the parser a better chance.
    """
    repairs: list[str] = []
    result = text.rstrip()

    # Track what needs to be closed
    stack: list[str] = []
    in_string = False
    escape_next = False

    for char in result:
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]" and stack and stack[-1] == char:
            stack.pop()

    # Close unclosed string
    if in_string:
        result += '"'
        repairs.append("string_completion")

    # Close unclosed structures
    while stack:
        result += stack.pop()
        repairs.append("brace_completion")

    return result, repairs
