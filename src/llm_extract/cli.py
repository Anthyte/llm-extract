"""Command-line interface for llm-extract."""

from __future__ import annotations

import argparse
import sys
from typing import Literal

import orjson

from .parser import extract_json_with_metadata


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command-line arguments. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        prog="llm-extract",
        description="Extract JSON from LLM output text. Fast. Simple. Reliable.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  llm-extract '{"key": "value"}'
  llm-extract -f response.txt
  echo '{"key": "value"}' | llm-extract
  llm-extract -f response.txt --pretty
  llm-extract -f response.txt --all --verbose
        """,
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "text",
        nargs="?",
        help="Text containing JSON to extract",
    )
    input_group.add_argument(
        "-f",
        "--file",
        type=str,
        help="File containing text to extract JSON from",
    )

    # Strategy options
    strategy_group = parser.add_mutually_exclusive_group()
    strategy_group.add_argument(
        "--strategy",
        choices=["first", "largest", "all"],
        default="first",
        help="Strategy for handling multiple JSON blocks (default: first)",
    )
    strategy_group.add_argument(
        "--all",
        action="store_true",
        help="Extract all JSON blocks (shorthand for --strategy all)",
    )
    strategy_group.add_argument(
        "--largest",
        action="store_true",
        help="Extract the largest JSON block (shorthand for --strategy largest)",
    )

    # Repair options
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="Disable JSON repair attempts",
    )

    # Output options
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output",
    )
    output_group.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (default)",
    )

    # Metadata options
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show extraction metadata",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    parsed_args = parser.parse_args(args)

    # Get input text
    text = _get_input_text(parsed_args)
    if text is None:
        print(
            "Error: No input provided. Use text argument, -f file, or pipe input.",
            file=sys.stderr,
        )
        return 1

    # Determine strategy
    strategy: Literal["first", "largest", "all"] = parsed_args.strategy
    if parsed_args.all:
        strategy = "all"
    elif parsed_args.largest:
        strategy = "largest"

    # Extract JSON
    result = extract_json_with_metadata(
        text,
        repair=not parsed_args.no_repair,
        strategy=strategy,
    )

    # Handle result
    if not result.success:
        error_msg = result.error.message if result.error else "Unknown error"
        print(f"Error: {error_msg}", file=sys.stderr)
        if parsed_args.verbose and result.candidates_found > 0:
            print(f"Candidates found: {result.candidates_found}", file=sys.stderr)
        return 1

    # Output JSON
    output = _format_output(result.data, pretty=parsed_args.pretty)
    print(output)

    # Show metadata if verbose
    if parsed_args.verbose:
        _print_metadata(result)

    return 0


def _get_input_text(args: argparse.Namespace) -> str | None:
    """Get input text from arguments, file, or stdin."""
    if args.text:
        return args.text

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return None
        except PermissionError:
            print(f"Error: Permission denied: {args.file}", file=sys.stderr)
            return None

    # Try stdin
    if not sys.stdin.isatty():
        return sys.stdin.read()

    return None


def _format_output(data: object, pretty: bool = False) -> str:
    """Format data as JSON string."""
    if pretty:
        return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
    return orjson.dumps(data).decode("utf-8")


def _print_metadata(result: object) -> None:
    """Print extraction metadata to stderr."""
    from .types import ExtractResult

    if not isinstance(result, ExtractResult):
        return

    print("\n--- Metadata ---", file=sys.stderr)
    print(f"Confidence: {result.confidence:.2f}", file=sys.stderr)
    if result.method:
        print(f"Method: {result.method.value}", file=sys.stderr)
    print(f"Candidates found: {result.candidates_found}", file=sys.stderr)
    if result.repairs_applied:
        print(f"Repairs applied: {', '.join(result.repairs_applied)}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
