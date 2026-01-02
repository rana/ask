"""Tests for CLI using Typer's CliRunner."""

from pathlib import Path

from typer.testing import CliRunner

from ask.cli import app
from ask.version import VERSION

runner = CliRunner()


class TestVersion:
    """Tests for version command and flag."""

    def test_version_command(self) -> None:
        """Version command shows version."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert VERSION in result.output

    def test_version_flag(self) -> None:
        """--version flag shows version and exits."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert VERSION in result.output

    def test_version_short_flag(self) -> None:
        """-V flag shows version and exits."""
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert VERSION in result.output


class TestHelp:
    """Tests for help output."""

    def test_help_flag(self) -> None:
        """--help shows command list."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "chat" in result.output
        assert "init" in result.output
        assert "apply" in result.output
        assert "check" in result.output
        assert "refresh" in result.output
        assert "cfg" in result.output

    def test_chat_help(self) -> None:
        """chat --help shows options."""
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "-m" in result.output

    def test_apply_help(self) -> None:
        """apply --help shows options."""
        result = runner.invoke(app, ["apply", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--files" in result.output
        assert "--commands" in result.output

    def test_check_help(self) -> None:
        """check --help shows options."""
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "--fix" in result.output

    def test_refresh_help(self) -> None:
        """refresh --help shows options."""
        result = runner.invoke(app, ["refresh", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--dry-run" in result.output

    def test_cfg_help(self) -> None:
        """cfg --help shows options."""
        result = runner.invoke(app, ["cfg", "--help"])
        assert result.exit_code == 0


class TestInit:
    """Tests for init command."""

    def test_init_creates_session(self, tmp_path: Path) -> None:
        """init creates session file."""
        session = tmp_path / "session.md"
        result = runner.invoke(app, ["init", str(session)])

        assert result.exit_code == 0
        assert session.exists()
        content = session.read_text()
        assert "# [1] Human" in content
        assert "_" in content

    def test_init_default_path(self, tmp_path: Path, monkeypatch: object) -> None:
        """init uses session.md as default."""

        # Change to tmp_path for default file creation
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert (tmp_path / "session.md").exists()

    def test_init_existing_file_fails(self, tmp_path: Path) -> None:
        """init fails if file exists."""
        session = tmp_path / "session.md"
        session.write_text("existing content")

        result = runner.invoke(app, ["init", str(session)])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_init_creates_directories(self, tmp_path: Path) -> None:
        """init creates parent directories."""
        session = tmp_path / "deep" / "nested" / "session.md"
        result = runner.invoke(app, ["init", str(session)])

        assert result.exit_code == 0
        assert session.exists()


class TestChatErrors:
    """Tests for chat command error handling."""

    def test_chat_missing_session(self, tmp_path: Path) -> None:
        """chat fails with missing session file."""
        session = tmp_path / "nonexistent.md"
        result = runner.invoke(app, ["chat", str(session)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "File not found" in result.output

    def test_chat_default_missing(self, tmp_path: Path, monkeypatch: object) -> None:
        """chat with default session.md missing shows helpful error."""
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

        result = runner.invoke(app, ["chat"])

        assert result.exit_code == 1
        assert "session.md" in result.output
        assert "init" in result.output


class TestApplyErrors:
    """Tests for apply command error handling."""

    def test_apply_missing_session(self, tmp_path: Path) -> None:
        """apply fails with missing session file."""
        session = tmp_path / "nonexistent.md"
        result = runner.invoke(app, ["apply", str(session)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "File not found" in result.output


class TestCheckErrors:
    """Tests for check command error handling."""

    def test_check_missing_session(self, tmp_path: Path) -> None:
        """check fails with missing session file."""
        session = tmp_path / "nonexistent.md"
        result = runner.invoke(app, ["check", str(session)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "File not found" in result.output


class TestRefreshErrors:
    """Tests for refresh command error handling."""

    def test_refresh_missing_session(self, tmp_path: Path) -> None:
        """refresh fails with missing session file."""
        session = tmp_path / "nonexistent.md"
        result = runner.invoke(app, ["refresh", str(session)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "File not found" in result.output


class TestCfg:
    """Tests for cfg command."""

    def test_cfg_shows_config(self, tmp_path: Path, monkeypatch: object) -> None:
        """cfg shows current configuration."""
        # Use tmp home to avoid touching real config
        monkeypatch.setenv("HOME", str(tmp_path))  # type: ignore[attr-defined]

        result = runner.invoke(app, ["cfg"])

        assert result.exit_code == 0
        assert "model" in result.output
        assert "temperature" in result.output

    def test_cfg_reset(self, tmp_path: Path, monkeypatch: object) -> None:
        """cfg reset resets to defaults."""
        monkeypatch.setenv("HOME", str(tmp_path))  # type: ignore[attr-defined]

        result = runner.invoke(app, ["cfg", "reset"])

        assert result.exit_code == 0
        assert "Reset" in result.output or "reset" in result.output

    def test_cfg_missing_value(self, tmp_path: Path, monkeypatch: object) -> None:
        """cfg with field but no value shows error."""
        monkeypatch.setenv("HOME", str(tmp_path))  # type: ignore[attr-defined]

        result = runner.invoke(app, ["cfg", "model"])

        assert result.exit_code == 1
        assert "Missing value" in result.output


class TestDefaultCommand:
    """Tests for default command behavior."""

    def test_no_args_runs_chat(self, tmp_path: Path, monkeypatch: object) -> None:
        """No arguments defaults to chat command."""
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

        # Should fail because no session.md exists, but proves chat was invoked
        result = runner.invoke(app, [])

        assert result.exit_code == 1
        assert "session.md" in result.output
