"""Tests for session management."""

import tempfile
from pathlib import Path

import pytest

from ask.errors import ParseError
from ask.session import (
    SessionWriter,
    read_session,
    turns_to_messages,
    validate_session,
)


def test_read_session_basic() -> None:
    """Read a basic session file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

What is Python?

_
""")
        f.flush()

        session = read_session(f.name)

        assert len(session.turns) == 1
        assert session.turns[0].role == "Human"
        assert session.last_human_turn_index == 0


def test_read_session_with_ai_response() -> None:
    """Read session with AI response."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

Question?

# [2] AI

``````markdown
Answer.
``````

# [3] Human

Follow-up.

_
""")
        f.flush()

        session = read_session(f.name)

        assert len(session.turns) == 3
        assert session.last_human_turn_index == 2


def test_read_session_file_not_found() -> None:
    """Reading non-existent file raises ParseError."""
    with pytest.raises(ParseError) as exc_info:
        read_session("/nonexistent/path/session.md")

    assert "not found" in str(exc_info.value)


def test_read_session_no_turns() -> None:
    """Empty session raises ParseError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Just some text, no turns.\n")
        f.flush()

        with pytest.raises(ParseError) as exc_info:
            read_session(f.name)

        assert "No turns" in str(exc_info.value)


def test_validate_session_ready() -> None:
    """Valid session passes validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

My question here.

_
""")
        f.flush()

        session = read_session(f.name)
        # Should not raise
        validate_session(session)


def test_validate_session_already_answered() -> None:
    """Session ending with AI turn fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

Question?

# [2] AI

``````markdown
Answer.
``````
""")
        f.flush()

        session = read_session(f.name)

        with pytest.raises(ParseError) as exc_info:
            validate_session(session)

        assert "already has AI response" in str(exc_info.value)


def test_validate_session_empty_human_turn() -> None:
    """Human turn with only marker fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

_
""")
        f.flush()

        session = read_session(f.name)

        with pytest.raises(ParseError) as exc_info:
            validate_session(session)

        assert "no content" in str(exc_info.value)


def test_turns_to_messages() -> None:
    """Convert turns to API messages."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

What is Python?

# [2] AI

``````markdown
Python is a language.
``````

# [3] Human

Tell me more.

_
""")
        f.flush()

        session = read_session(f.name)
        messages = turns_to_messages(session.turns)

        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"


def test_turns_to_messages_strips_underscore_marker() -> None:
    """Underscore marker should be stripped from messages."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

My question here.

_
""")
        f.flush()

        session = read_session(f.name)
        messages = turns_to_messages(session.turns)

        assert len(messages) == 1
        content = messages[0]["content"][0]["text"]
        assert "_" not in content
        assert "My question here." in content


def test_session_writer_creates_response() -> None:
    """SessionWriter creates properly formatted AI response."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

Question?

_
""")
        f.flush()
        path = f.name

    writer = SessionWriter(path, next_turn_number=2)
    writer.write("This is ")
    writer.write("the answer.")
    writer.end()

    result = Path(path).read_text()

    # Check AI turn header
    assert "# [2] AI" in result

    # Check 6-backtick wrapper
    assert "``````markdown" in result
    assert result.count("``````") == 2  # Opening and closing

    # Check content
    assert "This is the answer." in result

    # Check next human turn
    assert "# [3] Human" in result
    assert result.strip().endswith("_")


def test_session_writer_interrupted() -> None:
    """SessionWriter handles interruption."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# [1] Human

Question?
""")
        f.flush()
        path = f.name

    writer = SessionWriter(path, next_turn_number=2)
    writer.write("Partial response...")
    writer.end(interrupted=True)

    result = Path(path).read_text()

    assert "# [3] Human (interrupted)" in result


def test_session_writer_no_content() -> None:
    """SessionWriter with no content doesn't create empty turn."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        original = """# [1] Human

Question?
"""
        f.write(original)
        f.flush()
        path = f.name

    writer = SessionWriter(path, next_turn_number=2)
    # Don't write anything
    writer.end()

    result = Path(path).read_text()

    # Should be unchanged
    assert result == original
    assert "# [2] AI" not in result