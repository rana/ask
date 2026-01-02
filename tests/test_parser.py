"""Tests for session parser."""

from ask.parser import count_input_markers, find_input_marker, parse_turns


def test_parse_basic_two_turn_conversation() -> None:
    """Parse basic two-turn conversation."""
    content = """# [1] Human

What is Python?

# [2] AI

``````markdown
Python is a programming language.
``````
"""
    turns = parse_turns(content)

    assert len(turns) == 2
    assert turns[0].number == 1
    assert turns[0].role == "Human"
    assert "What is Python?" in turns[0].content
    assert turns[1].number == 2
    assert turns[1].role == "AI"
    assert "Python is a programming language." in turns[1].content


def test_parse_ignores_turn_headers_inside_code_fences() -> None:
    """Turn headers inside code fences should be ignored."""
    content = """# [1] Human

Here's some markdown:

```markdown
# [2] AI

This is not a real turn.
```

Actual question here.
"""
    turns = parse_turns(content)

    assert len(turns) == 1
    assert turns[0].number == 1
    assert turns[0].role == "Human"
    assert "# [2] AI" in turns[0].content  # The fake header is in content


def test_parse_ignores_turn_headers_inside_file_markers() -> None:
    """Turn headers inside blocks should be ignored."""
    content = """# [1] Human

### test.md
```markdown
# [2] AI

Fake turn in file.
```
My question.
"""
    turns = parse_turns(content)

    assert len(turns) == 1
    assert turns[0].number == 1
    assert turns[0].role == "Human"


def test_ai_response_unwrapped_from_six_backticks() -> None:
    """AI response should be unwrapped from exactly 6 backticks."""
    content = """# [1] Human

Question?

# [2] AI

``````markdown
The answer is 42.

```python
x = 42
```
``````
"""
    turns = parse_turns(content)

    assert len(turns) == 2
    assert turns[1].role == "AI"
    # Content should be unwrapped
    assert "The answer is 42." in turns[1].content
    assert "```python" in turns[1].content
    # Wrapper should be removed
    assert "``````markdown" not in turns[1].content


def test_ai_response_with_five_backtick_fence_preserved() -> None:
    """Fences with fewer than 6 backticks inside AI response should be preserved."""
    content = """# [1] Human

Show code.

# [2] AI

``````markdown
Here's code:

`````python
def foo():
    pass
`````
``````
"""
    turns = parse_turns(content)

    assert len(turns) == 2
    assert "`````python" in turns[1].content
    assert "def foo():" in turns[1].content


def test_parse_empty_content() -> None:
    """Empty content should return no turns."""
    turns = parse_turns("")
    assert turns == []


def test_parse_no_turns() -> None:
    """Content without turn headers should return no turns."""
    content = "Just some text without any turn headers."
    turns = parse_turns(content)
    assert turns == []


def test_parse_multiple_human_turns() -> None:
    """Parse conversation with multiple human turns."""
    content = """# [1] Human

First question.

# [2] AI

``````markdown
First answer.
``````

# [3] Human

Follow-up question.

_
"""
    turns = parse_turns(content)

    assert len(turns) == 3
    assert turns[0].role == "Human"
    assert turns[1].role == "AI"
    assert turns[2].role == "Human"
    assert "Follow-up question." in turns[2].content


def test_find_input_marker() -> None:
    """Find the underscore input marker."""
    content = """# [1] Human

My question.

_
"""
    result = find_input_marker(content)

    assert result is not None
    line_idx, _ = result
    assert line_idx == 4  # 0-indexed: header, blank, question, blank, marker


def test_find_input_marker_not_in_code_fence() -> None:
    """Input marker inside code fence should not be found."""
    content = """# [1] Human

```
_
```

Actual marker below:

_
"""
    result = find_input_marker(content)

    assert result is not None
    line_idx, _ = result
    # Should find the marker outside the fence, not inside
    assert line_idx == 8


def test_count_input_markers() -> None:
    """Count input markers outside excluded regions."""
    content = """# [1] Human

_

```
_
```

_
"""
    count = count_input_markers(content)

    # Two real markers, one inside code fence (ignored)
    assert count == 2


def test_count_input_markers_none() -> None:
    """No markers should return 0."""
    content = """# [1] Human

No marker here.
"""
    count = count_input_markers(content)
    assert count == 0
