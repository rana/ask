"""Session management for ask."""

from __future__ import annotations

from pathlib import Path

from ask.config import load_config
from ask.errors import ParseError
from ask.expand import expand_references
from ask.parser import parse_turns
from ask.types import Message, MessageContent, Session, Turn


def read_session(path: str) -> Session:
    """Read and parse a session file.

    Raises ParseError if the file cannot be read or parsed.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise ParseError(f"Session file not found: {path}")

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ParseError(f"Cannot read session file: {e}") from e

    turns = parse_turns(content)

    if not turns:
        raise ParseError("No turns in session", "Add a turn header like: # [1] Human")

    # Find last human turn index
    last_human_idx = -1
    for i, turn in enumerate(turns):
        if turn.role == "Human":
            last_human_idx = i

    if last_human_idx == -1:
        raise ParseError("No human turn found", "Session must have at least one human turn")

    return Session(turns=turns, last_human_turn_index=last_human_idx)


def validate_session(session: Session) -> None:
    """Validate session is ready for AI response.

    Raises ParseError if:
    - Last turn is AI (already answered)
    - Last human turn has no content
    """
    if not session.turns:
        raise ParseError("No turns in session")

    last_turn = session.turns[-1]

    if last_turn.role == "AI":
        raise ParseError(
            "Session already has AI response",
            "Add a new human turn before running ask",
        )

    # Check last human turn has content (not just underscore marker)
    last_human = session.turns[session.last_human_turn_index]
    content = last_human.content.strip()

    # Remove underscore marker for content check
    if content == "_":
        raise ParseError(
            f"Turn {last_human.number} has no content",
            "Add your question before the _ marker",
        )

    # Content with just underscore at end is valid
    # Content must have something besides underscore
    content_without_marker = content.replace("_", "").strip()
    if not content_without_marker:
        raise ParseError(
            f"Turn {last_human.number} has no content",
            "Add your question before the _ marker",
        )


def expand_and_save_session(path: str, session: Session) -> tuple[bool, int]:
    """Expand references in last human turn and save if changed.

    Returns (was_expanded, file_count).
    """
    config = load_config()

    last_human = session.turns[session.last_human_turn_index]

    # Check if there are any references to expand
    if "[[" not in last_human.content:
        return False, 0

    expanded_content, file_count = expand_references(last_human.content, config)

    if expanded_content == last_human.content:
        return False, 0

    # Read original file and replace the turn content
    file_path = Path(path)
    original = file_path.read_text(encoding="utf-8")

    # Find and replace the turn content
    # We need to find the turn header and replace everything until next turn or EOF
    lines = original.split("\n")
    turn_header = f"# [{last_human.number}] Human"

    start_idx: int | None = None
    end_idx: int | None = None

    for i, line in enumerate(lines):
        if line.strip() == turn_header:
            start_idx = i
        elif start_idx is not None and line.startswith("# [") and "] " in line:
            end_idx = i
            break

    if start_idx is None:
        return False, 0

    if end_idx is None:
        end_idx = len(lines)

    # Rebuild the file
    new_lines = lines[: start_idx + 1]  # Include the turn header
    new_lines.append("")  # Blank line after header
    new_lines.append(expanded_content)
    new_lines.extend(lines[end_idx:])

    new_content = "\n".join(new_lines)
    file_path.write_text(new_content, encoding="utf-8")

    return True, file_count


def turns_to_messages(turns: list[Turn]) -> list[Message]:
    """Convert turns to API message format."""
    messages: list[Message] = []

    for turn in turns:
        role: str = "user" if turn.role == "Human" else "assistant"

        # Remove the underscore marker from content for API
        content = turn.content
        if content.endswith("\n_"):
            content = content[:-2].rstrip()
        elif content.endswith("_"):
            content = content[:-1].rstrip()

        # Skip empty content
        if not content.strip():
            continue

        message: Message = {
            "role": role,  # type: ignore[typeddict-item]
            "content": [MessageContent(text=content)],
        }
        messages.append(message)

    return messages


class SessionWriter:
    """Writes AI response to session file incrementally."""

    def __init__(self, path: str, next_turn_number: int) -> None:
        self.path = Path(path)
        self.next_turn_number = next_turn_number
        self.buffer: list[str] = []
        self._started = False
        self._file_handle = open(self.path, "a", encoding="utf-8")  # noqa: SIM115

    def write(self, text: str) -> None:
        """Write a chunk of AI response."""
        if not self._started:
            self._start_response()
            self._started = True

        self.buffer.append(text)
        self._file_handle.write(text)
        self._file_handle.flush()

    def _start_response(self) -> None:
        """Write the AI turn header and opening wrapper."""
        header = f"\n# [{self.next_turn_number}] AI\n\n``````markdown\n"
        self._file_handle.write(header)
        self._file_handle.flush()

    def end(self, interrupted: bool = False) -> None:
        """Finalize the response and append next human turn."""
        if not self._started:
            # No content was written, don't create empty turn
            self._file_handle.close()
            return

        # Close the 6-backtick wrapper
        self._file_handle.write("\n``````\n")

        # Append next human turn
        next_human_number = self.next_turn_number + 1
        suffix = " (interrupted)" if interrupted else ""
        human_turn = f"\n# [{next_human_number}] Human{suffix}\n\n_\n"
        self._file_handle.write(human_turn)

        self._file_handle.close()