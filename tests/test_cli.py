"""Tests for llm_extract.cli module."""

import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from llm_extract.cli import _format_output, _get_input_text, _print_metadata, main
from llm_extract.types import ExtractionMethod, ExtractResult


class TestMain:
    """Tests for main CLI function."""

    def test_simple_json_argument(self) -> None:
        """Test extracting JSON from command line argument."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = main(['{"key": "value"}'])
        assert exit_code == 0
        assert '{"key":"value"}' in mock_stdout.getvalue()

    def test_json_from_file(self) -> None:
        """Test extracting JSON from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()
            filepath = f.name

        try:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = main(["-f", filepath])
            assert exit_code == 0
            assert '{"key":"value"}' in mock_stdout.getvalue()
        finally:
            Path(filepath).unlink()

    def test_json_from_stdin(self) -> None:
        """Test extracting JSON from stdin."""
        with (
            patch("sys.stdin", StringIO('{"key": "value"}')),
            patch("sys.stdin.isatty", return_value=False),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            exit_code = main([])
        assert exit_code == 0
        assert '{"key":"value"}' in mock_stdout.getvalue()

    def test_no_input_error(self) -> None:
        """Test error when no input provided."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            exit_code = main([])
        assert exit_code == 1
        assert "No input provided" in mock_stderr.getvalue()

    def test_file_not_found(self) -> None:
        """Test error when file not found."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            exit_code = main(["-f", "/nonexistent/file.txt"])
        assert exit_code == 1
        assert "File not found" in mock_stderr.getvalue()

    def test_invalid_json_error(self) -> None:
        """Test error message for invalid JSON."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            exit_code = main(["not json at all"])
        assert exit_code == 1
        assert "Error:" in mock_stderr.getvalue()

    def test_pretty_output(self) -> None:
        """Test pretty-printed output."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = main(['{"key": "value"}', "--pretty"])
        assert exit_code == 0
        output = mock_stdout.getvalue()
        assert "\n" in output  # Pretty print has newlines

    def test_compact_output(self) -> None:
        """Test compact output (default)."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = main(['{"key": "value"}', "--compact"])
        assert exit_code == 0
        output = mock_stdout.getvalue().strip()
        assert output == '{"key":"value"}'

    def test_no_repair_flag(self) -> None:
        """Test --no-repair flag."""
        with patch("sys.stderr", new_callable=StringIO):
            exit_code = main(['{"key": "value",}', "--no-repair"])
        assert exit_code == 1  # Should fail without repair

    def test_strategy_all(self) -> None:
        """Test --all flag."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = main(['{"a": 1} and {"b": 2}', "--all"])
        assert exit_code == 0
        assert "[" in mock_stdout.getvalue()  # Should be array

    def test_strategy_largest(self) -> None:
        """Test --largest flag."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = main(['{"a": 1} and {"b": 2, "c": 3}', "--largest"])
        assert exit_code == 0
        output = mock_stdout.getvalue()
        assert '"b"' in output
        assert '"c"' in output

    def test_strategy_option(self) -> None:
        """Test --strategy option."""
        with patch("sys.stdout", new_callable=StringIO):
            exit_code = main(['{"a": 1}', "--strategy", "first"])
        assert exit_code == 0

    def test_verbose_flag(self) -> None:
        """Test --verbose flag shows metadata."""
        with (
            patch("sys.stdout", new_callable=StringIO),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            exit_code = main(['{"key": "value"}', "--verbose"])
        assert exit_code == 0
        stderr_output = mock_stderr.getvalue()
        assert "Confidence:" in stderr_output
        assert "Method:" in stderr_output

    def test_verbose_with_repairs(self) -> None:
        """Test verbose output shows repairs."""
        with (
            patch("sys.stdout", new_callable=StringIO),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            exit_code = main(['{"key": "value",}', "--verbose"])
        assert exit_code == 0
        assert "Repairs applied:" in mock_stderr.getvalue()

    def test_verbose_on_error(self) -> None:
        """Test verbose shows candidates on error."""
        # Create a situation where candidates are found but parsing fails
        with patch("sys.stderr", new_callable=StringIO):
            exit_code = main(["{invalid json}", "--verbose", "--no-repair"])
        assert exit_code == 1


class TestFormatOutput:
    """Tests for _format_output function."""

    def test_compact_format(self) -> None:
        """Test compact JSON format."""
        data = {"key": "value", "num": 42}
        result = _format_output(data, pretty=False)
        assert result == '{"key":"value","num":42}'

    def test_pretty_format(self) -> None:
        """Test pretty JSON format."""
        data = {"key": "value"}
        result = _format_output(data, pretty=True)
        assert "\n" in result
        assert "  " in result  # Indentation

    def test_array_format(self) -> None:
        """Test array formatting."""
        data = [1, 2, 3]
        result = _format_output(data, pretty=False)
        assert result == "[1,2,3]"


class TestGetInputText:
    """Tests for _get_input_text function."""

    def test_text_argument(self) -> None:
        """Test getting text from argument."""
        import argparse

        args = argparse.Namespace(text="test text", file=None)
        result = _get_input_text(args)
        assert result == "test text"

    def test_file_argument(self) -> None:
        """Test getting text from file."""
        import argparse

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file content")
            f.flush()
            filepath = f.name

        try:
            args = argparse.Namespace(text=None, file=filepath)
            result = _get_input_text(args)
            assert result == "file content"
        finally:
            Path(filepath).unlink()

    def test_stdin(self) -> None:
        """Test getting text from stdin."""
        import argparse

        args = argparse.Namespace(text=None, file=None)
        with (
            patch("sys.stdin", StringIO("stdin content")),
            patch("sys.stdin.isatty", return_value=False),
        ):
            result = _get_input_text(args)
        assert result == "stdin content"

    def test_no_input(self) -> None:
        """Test when no input is available."""
        import argparse

        args = argparse.Namespace(text=None, file=None)
        with patch("sys.stdin.isatty", return_value=True):
            result = _get_input_text(args)
        assert result is None

    def test_file_permission_error(self) -> None:
        """Test handling of permission error."""
        import argparse
        from unittest.mock import mock_open

        args = argparse.Namespace(text=None, file="test.txt")
        # Mock open to raise PermissionError
        with patch("builtins.open", mock_open()) as mocked_open:
            mocked_open.side_effect = PermissionError("Permission denied")
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                result = _get_input_text(args)
        assert result is None
        assert "Permission denied" in mock_stderr.getvalue()


class TestPrintMetadata:
    """Tests for _print_metadata function."""

    def test_print_basic_metadata(self) -> None:
        """Test printing basic metadata."""
        result = ExtractResult(
            success=True,
            data={"key": "value"},
            confidence=0.95,
            method=ExtractionMethod.MARKDOWN_FENCE,
            candidates_found=2,
        )
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            _print_metadata(result)
        output = mock_stderr.getvalue()
        assert "0.95" in output
        assert "markdown_fence" in output
        assert "2" in output

    def test_print_with_repairs(self) -> None:
        """Test printing metadata with repairs."""
        result = ExtractResult(
            success=True,
            data={"key": "value"},
            confidence=0.9,
            method=ExtractionMethod.BRACE_MATCH,
            repairs_applied=["trailing_comma_removal", "quote_normalization"],
            candidates_found=1,
        )
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            _print_metadata(result)
        output = mock_stderr.getvalue()
        assert "trailing_comma_removal" in output
        assert "quote_normalization" in output

    def test_print_non_result_object(self) -> None:
        """Test that non-ExtractResult objects are handled."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            _print_metadata("not a result")
        assert mock_stderr.getvalue() == ""

    def test_print_without_method(self) -> None:
        """Test printing when method is None."""
        result = ExtractResult(
            success=True,
            data={"key": "value"},
            confidence=0.5,
            method=None,
            candidates_found=1,
        )
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            _print_metadata(result)
        output = mock_stderr.getvalue()
        assert "Method:" not in output
