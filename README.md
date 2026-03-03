# ai-extract

> Extract structured data from any AI response. Fast. Simple. Reliable.

[![PyPI version](https://badge.fury.io/py/ai-extract.svg?icon=si%3Apython)](https://badge.fury.io/py/ai-extract)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ai-extract** is a fast, lightweight Python library for extracting JSON from AI outputs. It handles markdown fences, surrounding text, and multiple JSON blocks.

## Features

- **Fast**: Uses `orjson` for 10x faster JSON parsing
- **Reliable**: Multiple extraction strategies with automatic fallback
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

### Multiple JSON Blocks

```python
# Get first JSON (default)
data = extract_json('{"a": 1} and {"b": 2}')
# Returns: {'a': 1}

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

### `extract_json(text, *, strategy="first", raise_on_error=True)`

Extract JSON from text.

**Parameters:**
- `text` (str): Text containing JSON
- `strategy` (str): How to handle multiple JSON blocks
  - `"first"`: Return first valid JSON (default)
  - `"all"`: Return list of all JSON blocks
- `raise_on_error` (bool): Raise ExtractError on failure (default: True)

**Returns:** Parsed JSON data, or list if strategy="all", or None if raise_on_error=False

## Extraction Methods

The library tries multiple strategies in order:

1. **Direct Parse** - Try parsing entire input as JSON
2. **Markdown Fence** - Extract from ```json blocks
3. **Brace Matching** - Find balanced {...} or [...]
4. **Heuristic** - Pattern matching after "Here's the JSON:" etc.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Rahul Vishwakarma ([@rvv-karma](https://github.com/rvv-karma))
