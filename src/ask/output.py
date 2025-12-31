"""Output formatting utilities."""

from __future__ import annotations

import sys


class Output:
    """Formatted output helpers."""

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"

    def success(self, msg: str) -> None:
        """Print success message."""
        self._print(f"{self.GREEN}✓{self.RESET} {msg}")

    def warning(self, msg: str) -> None:
        """Print warning message."""
        self._print(f"{self.YELLOW}⚠{self.RESET} {msg}")

    def error(self, msg: str) -> None:
        """Print error message."""
        self._print_err(f"{self.RED}✗{self.RESET} {msg}")

    def info(self, msg: str) -> None:
        """Print info message."""
        self._print(msg)

    def blank(self) -> None:
        """Print blank line."""
        self._print("")

    def dim(self, text: str) -> str:
        """Return dimmed text."""
        return f"{self.DIM}{text}{self.RESET}"

    def bold(self, text: str) -> str:
        """Return bold text."""
        return f"{self.BOLD}{text}{self.RESET}"

    def cyan(self, text: str) -> str:
        """Return cyan text."""
        return f"{self.CYAN}{text}{self.RESET}"

    def green(self, text: str) -> str:
        """Return green text."""
        return f"{self.GREEN}{text}{self.RESET}"

    def number(self, n: int) -> str:
        """Format number with locale separators."""
        return f"{n:,}"

    def model_name(self, model_id: str) -> str:
        """Format model name for display."""
        import re

        name = re.sub(r"^anthropic\.", "", model_id)
        name = re.sub(r"-\d{8}.*$", "", name)
        name = re.sub(r"-v\d+:\d+$", "", name)
        return f"{self.CYAN}{name}{self.RESET}"

    def field(self, key: str, value: str, width: int = 12) -> None:
        """Print a key-value field."""
        padded_key = f"{key}:".rjust(width)
        self._print(f"{self.CYAN}{padded_key}{self.RESET} {value}")

    def field_dim(self, key: str, value: str, width: int = 12) -> None:
        """Print a key-value field with dim value."""
        padded_key = f"{key}:".rjust(width)
        self._print(f"{self.CYAN}{padded_key}{self.RESET} {self.DIM}{value}{self.RESET}")

    def meta(self, items: list[tuple[str, str | int]]) -> None:
        """Print metadata items."""
        formatted: list[str] = []
        for key, val in items:
            val_str = f"{val:,}" if isinstance(val, int) else val
            formatted.append(f"{self.DIM}{key}:{self.RESET} {val_str}")
        sep = f"{self.DIM}  ·  {self.RESET}"
        self._print(f"  {sep.join(formatted)}")

    def progress(self, msg: str) -> None:
        """Print progress message (overwrites line)."""
        sys.stdout.write(f"\r\033[K{msg}")
        sys.stdout.flush()

    def clear_line(self) -> None:
        """Clear the current line."""
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def write(self, msg: str) -> None:
        """Write without newline."""
        sys.stdout.write(msg)
        sys.stdout.flush()

    def _print(self, msg: str) -> None:
        """Print to stdout."""
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()

    def _print_err(self, msg: str) -> None:
        """Print to stderr."""
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


output = Output()
