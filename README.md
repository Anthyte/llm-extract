# ai-extract

> Extract structured data from any AI response. Fast. Simple. Reliable.

[![PyPI version](https://badge.fury.io/py/ai-extract.svg)](https://badge.fury.io/py/ai-extract)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ai-extract** is a fast, lightweight Python library for extracting JSON from messy AI outputs. It handles markdown fences, surrounding text, malformed JSON, and more.

## Features

- **Fast**: Uses `orjson` for 10x faster JSON parsing
- **Reliable**: Multiple extraction strategies with automatic fallback
- **Smart Repair**: Fixes common AI JSON errors (trailing commas, single quotes, unquoted keys)
- **Simple API**: One function for most use cases
- **CLI Tool**: Quick extraction from command line
- **Zero Config**: Works out of the box

## Installation

```bash
pip install ai-extract
```

## Quick Start

```python
from ai_extract import extract_json

# Extract from messy AI output
text = """
Here's the JSON you requested:
```json
{"name": "John", "age": 30}
```
Hope this helps!
"""

data = extract_json(text)
print(data)  # {'name': 'John', 'age': 30}
```

## Usage Examples

### Basic Extraction

```python
from ai_extract import extract_json

# Pure JSON
data = extract_json('{"key": "value"}')

# JSON in text
data = extract_json('The result is: {"success": true}')

# JSON in markdown fence
data = extract_json('```json\n{"data": [1,2,3]}\n```')
```

### Auto-Repair Malformed JSON

```python
# Trailing commas (common AI error)
data = extract_json('{"items": [1, 2, 3,],}')
# Returns: {'items': [1, 2, 3]}

# Single quotes (Python-style)
data = extract_json("{'key': 'value'}")
# Returns: {'key': 'value'}

# Unquoted keys (JavaScript-style)
data = extract_json('{key: "value"}')
# Returns: {'key': 'value'}
```

### Multiple JSON Blocks

```python
# Get first JSON (default)
data = extract_json('{"a": 1} and {"b": 2}')
# Returns: {'a': 1}

# Get largest JSON
data = extract_json('{"a": 1} and {"b": 2, "c": 3}', strategy="largest")
# Returns: {'b': 2, 'c': 3}

# Get all JSON blocks
data = extract_json('{"a": 1} and {"b": 2}', strategy="all")
# Returns: [{'a': 1}, {'b': 2}]
```

### Error Handling

```python
from ai_extract import extract_json, ExtractError

# Raise exception (default)
try:
    data = extract_json("no json here")
except ExtractError as e:
    print(f"Error: {e.message}")
    print(f"Type: {e.error_type}")

# Return None instead
data = extract_json("no json here", raise_on_error=False)
# Returns: None
```

### Get Extraction Metadata

```python
from ai_extract import extract_json_with_metadata

result = extract_json_with_metadata('```json\n{"key": "value"}\n```')

print(result.success)        # True
print(result.data)           # {'key': 'value'}
print(result.confidence)     # 0.95
print(result.method)         # ExtractionMethod.MARKDOWN_FENCE
print(result.repairs_applied)  # []
```

## CLI Usage

```bash
# From argument
ai-extract '{"key": "value"}'

# From file
ai-extract -f response.txt

# From stdin
echo '{"key": "value"}' | ai-extract

# Pretty print
ai-extract -f response.txt --pretty

# Get all JSON blocks
ai-extract -f response.txt --all

# Show metadata
ai-extract -f response.txt --verbose
```

## API Reference

### `extract_json(text, *, repair=True, strategy="first", raise_on_error=True)`

Extract JSON from text.

**Parameters:**
- `text` (str): Text containing JSON
- `repair` (bool): Enable auto-repair of malformed JSON (default: True)
- `strategy` (str): How to handle multiple JSON blocks
  - `"first"`: Return first valid JSON (default)
  - `"largest"`: Return largest JSON structure
  - `"all"`: Return list of all JSON blocks
- `raise_on_error` (bool): Raise ExtractError on failure (default: True)

**Returns:** Parsed JSON data, or list if strategy="all", or None if raise_on_error=False

### `extract_json_with_metadata(text, *, repair=True, strategy="first")`

Extract JSON with detailed metadata.

**Returns:** `ExtractResult` with fields:
- `success` (bool): Whether extraction succeeded
- `data` (Any): Parsed JSON data
- `raw_json` (str): Raw JSON string before parsing
- `confidence` (float): Confidence score (0.0-1.0)
- `method` (ExtractionMethod): How JSON was found
- `repairs_applied` (list[str]): List of repairs performed
- `candidates_found` (int): Number of JSON candidates found
- `error` (ExtractError): Error details if failed

## Extraction Methods

The library tries multiple strategies in order:

1. **Direct Parse** (confidence: 1.0) - Try parsing entire input as JSON
2. **Markdown Fence** (confidence: 0.95) - Extract from ```json blocks
3. **Brace Matching** (confidence: 0.8) - Find balanced {...} or [...]
4. **Heuristic** (confidence: 0.6) - Pattern matching after "Here's the JSON:" etc.

## Repair Strategies

Safe repairs applied automatically:
- Remove trailing commas
- Convert single quotes to double quotes
- Quote unquoted keys
- Remove BOM and invisible characters
- Complete truncated JSON (marked in metadata)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Rahul Vishwakarma ([@rvv-karma](https://github.com/rvv-karma))
