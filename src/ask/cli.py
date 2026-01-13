"""CLI entry point for ask using Typer."""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Annotated

import typer

from ask.apply import apply_session, format_applied_block, insert_applied_block
from ask.bedrock import extract_region, find_profile, stream_completion
from ask.check import check_session
from ask.config import ensure_config, get_config_path, load_config, save_config, update_config
from ask.errors import AskError, ConfigError
from ask.output import output
from ask.refresh import print_refresh_result, refresh_session
from ask.session import (
    SessionWriter,
    expand_session,
    read_session,
    turns_to_messages,
    validate_session,
)
from ask.tokens import estimate_tokens
from ask.types import Config, ModelType, StreamChunk, StreamEnd
from ask.version import get_version_string
from ask.workspace import find_workspace

app = typer.Typer(
    name="ask",
    help="AI conversations through Markdown files",
    add_completion=False,
    no_args_is_help=False,
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        output.info(get_version_string())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """ask — AI conversations through Markdown files."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@app.command()
def chat(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    model: Annotated[
        ModelType | None,
        typer.Option("-m", "--model", help="Model to use (opus/sonnet/haiku)"),
    ] = None,
) -> None:
    """Continue the conversation with AI."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        config = load_config()
        model_type = model or config.model

        sess = read_session(str(session))
        validate_session(sess)

        profile = find_profile(model_type)
        region = extract_region(profile)

        output.meta(
            [("Model", f"{output.model_name(profile.model_id)} {output.dim(f'({region})')}")]
        )

        messages = turns_to_messages(sess.turns)
        input_tokens = estimate_tokens(messages)
        turn_label = "turn" if len(sess.turns) == 1 else "turns"

        output.meta(
            [
                ("Input", f"{output.number(input_tokens)} tokens"),
                ("Turns", f"{len(sess.turns)} {turn_label}"),
            ]
        )

        if input_tokens > 150000:
            output.blank()
            output.warning("Large input may be slow or hit limits")

        next_turn_number = sess.turns[-1].number + 1
        writer = SessionWriter(str(session), next_turn_number)

        final_tokens = 0
        interrupted = False

        def handle_interrupt(signum: int, frame: object) -> None:
            nonlocal interrupted
            interrupted = True

        signal.signal(signal.SIGINT, handle_interrupt)

        output.blank()
        output.write(output.dim("Streaming... "))

        max_tokens = config.max_tokens or 32000
        for event in stream_completion(
            profile.arn,
            messages,
            max_tokens,
            config.temperature,
        ):
            if interrupted:
                break

            if isinstance(event, StreamChunk):
                writer.write(event.text)
                final_tokens = event.tokens
                output.progress(
                    f"{output.dim('Streaming')} "
                    f"{output.cyan(output.number(final_tokens))} "
                    f"{output.dim('tokens')}"
                )
            elif isinstance(event, StreamEnd):
                final_tokens = event.total_tokens

        writer.end(interrupted)

        output.clear_line()
        if interrupted:
            output.warning(f"Interrupted at {output.cyan(output.number(final_tokens))} tokens")
        else:
            output.success(
                f"Done {output.dim('·')} {output.cyan(output.number(final_tokens))} tokens"
            )

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(help="Path for session file"),
    ] = Path("session.md"),
) -> None:
    """Initialize a new session file."""
    file_path = path

    if str(path).endswith("/") or str(path).endswith("\\"):
        file_path = path / "session.md"

    if file_path.exists() and file_path.is_dir():
        file_path = file_path / "session.md"

    if file_path.exists():
        output.error(f"{file_path} already exists")
        output.info("Delete it to start fresh")
        raise typer.Exit(1)

    file_path.parent.mkdir(parents=True, exist_ok=True)

    content = "# [1] Human\n\n_\n"
    file_path.write_text(content, encoding="utf-8")

    output.success(f"Created {file_path}")

    try:
        ensure_config()
    except Exception as e:
        output.warning(f"Could not create config file: {e}")

    output.blank()
    output.info("Next steps:")
    output.info(f"1. Add your question to {file_path}")
    cmd_suffix = "" if str(file_path) == "session.md" else f" {file_path}"
    output.info(f"2. Run: ask{cmd_suffix}")


@app.command(name="expand")
def expand_cmd(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
) -> None:
    """Expand [[references]] in the last human turn."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        _, file_count = expand_session(str(session))

        output.success(f"Expanded {file_count} file{'s' if file_count != 1 else ''}")
        output.info(output.dim(f"Updated {session}"))

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command(name="apply")
def apply_cmd(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without writing or executing"),
    ] = False,
    files: Annotated[
        bool,
        typer.Option("--files", help="Apply only file blocks"),
    ] = False,
    commands: Annotated[
        bool,
        typer.Option("--commands", help="Apply only command blocks"),
    ] = False,
) -> None:
    """Apply files and commands from AI response."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        apply_files = True
        apply_commands = True

        if files:
            apply_commands = False
        elif commands:
            apply_files = False

        session_content = session.read_text(encoding="utf-8")
        workspace = find_workspace(session_content)

        if dry_run:
            output.info(output.dim("Dry run - no changes will be made"))
            output.blank()

        if workspace:
            output.meta([("Workspace", str(workspace))])

        result = apply_session(
            str(session),
            dry_run=dry_run,
            apply_files=apply_files,
            apply_commands=apply_commands,
        )

        if result.file_results:
            output.blank()
            for fr in result.file_results:
                if fr.error:
                    output.error(f"{fr.path} - {fr.error}")
                else:
                    action_color = output.green if fr.action == "created" else output.cyan
                    output.success(
                        f"{fr.path} {output.dim('·')} "
                        f"{action_color(fr.action)} {output.dim(f'({fr.size}B)')}"
                    )

        if result.command_results:
            output.blank()
            for cr in result.command_results:
                if cr.status == "OK":
                    output.success(f"{output.dim('$')} {cr.command}")
                else:
                    output.error(f"{output.dim('$')} {cr.command}")
                    if cr.output:
                        for line in cr.output.split("\n")[:5]:
                            output.info(f"  {output.dim(line)}")

        output.blank()
        file_count = len(result.file_results)
        cmd_count = len(result.command_results)

        if dry_run:
            parts: list[str] = []
            if file_count:
                parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
            if cmd_count:
                parts.append(f"{cmd_count} command{'s' if cmd_count != 1 else ''}")
            output.info(f"Would apply: {', '.join(parts)}")
        else:
            if result.status == "OK":
                parts = []
                if file_count:
                    parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
                if cmd_count:
                    parts.append(f"{cmd_count} command{'s' if cmd_count != 1 else ''}")
                output.success(f"Applied {', '.join(parts)}")

                applied_block = format_applied_block(result)
                insert_applied_block(str(session), applied_block)
                output.info(output.dim(f"Updated {session}"))
            else:
                output.warning("Apply completed with errors")

                applied_block = format_applied_block(result)
                insert_applied_block(str(session), applied_block)
                output.info(output.dim(f"Updated {session}"))

        if result.status != "OK":
            raise typer.Exit(1)

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command(name="check")
def check_cmd(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Run auto-fix commands before checking"),
    ] = False,
) -> None:
    """Run verification checks (lint, type check, tests)."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        session_content = session.read_text(encoding="utf-8")
        workspace = find_workspace(session_content)

        if workspace:
            output.meta([("Workspace", str(workspace))])

        if fix:
            output.info(output.dim("Running fixes first..."))

        output.blank()
        output.info(output.dim("Running checks..."))

        result = check_session(str(session), fix=fix)

        output.blank()
        for r in result.results:
            if r.status == "PASS":
                summary_text = f" {output.dim(f'({r.summary})')}" if r.summary else ""
                output.success(f"{r.id}{summary_text}")
            elif r.status == "FAIL":
                summary_text = f" {output.dim(f'({r.summary})')}" if r.summary else ""
                output.error(f"{r.id}{summary_text}")
            elif r.status == "TIMEOUT":
                output.warning(f"{r.id} {output.dim('(timeout)')}")
            else:
                output.error(f"{r.id} {output.dim(f'({r.summary})')}")

        output.blank()
        if result.status == "PASS":
            output.success("All checks passed")
        else:
            fail_count = sum(1 for r in result.results if r.status != "PASS")
            output.error(f"{fail_count} check{'s' if fail_count != 1 else ''} failed")

        output.info(output.dim(f"Updated {session}"))

        if result.status != "PASS":
            raise typer.Exit(1)

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command()
def refresh(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    url: Annotated[
        bool,
        typer.Option("--url", help="Also refresh URL blocks (default: skip)"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without modifying file"),
    ] = False,
) -> None:
    """Re-expand all marked references in place."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        if dry_run:
            output.info(output.dim("Dry run - no changes will be made"))
            output.blank()

        result = refresh_session(
            str(session),
            include_urls=url,
            dry_run=dry_run,
        )

        print_refresh_result(result, dry_run=dry_run)

        if not dry_run and (
            result.files_refreshed > 0 or result.dirs_refreshed > 0 or result.urls_refreshed > 0
        ):
            output.info(output.dim(f"Updated {session}"))

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command()
def cfg(
    field: Annotated[
        str | None,
        typer.Argument(help="Config field or 'reset'"),
    ] = None,
    value: Annotated[
        str | None,
        typer.Argument(help="Value to set"),
    ] = None,
) -> None:
    """View or update configuration."""
    try:
        if not field:
            ensure_config()
            config = load_config()
            config_path = get_config_path()

            output.info(output.dim(f"Config: {config_path}"))

            output.field("model", config.model)
            output.field("temperature", str(config.temperature))

            if config.max_tokens:
                output.field("maxTokens", str(config.max_tokens))
            else:
                output.field_dim("maxTokens", "(AWS default)")

            if config.region:
                output.field("region", config.region)
            else:
                output.field_dim("region", "(no preference)")

            output.field("filter", "on" if config.filter else "off")

            exclude = config.exclude or Config.default_exclude()
            output.field("exclude", f"{len(exclude)} patterns")

            return

        if field == "reset":
            save_config(Config())
            output.success("Reset to defaults")
            return

        if not value:
            output.error(f"Missing value for '{field}'")
            output.info(f"Usage: ask cfg {field} <value>")
            raise typer.Exit(1)

        update_config(field, value)
        output.success(f"{field} set to {value}")

    except ConfigError as e:
        output.error(e.message)
        if e.help_text:
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        output.error(str(e))
        raise typer.Exit(1) from None


@app.command()
def version() -> None:
    """Show version information."""
    output.info(get_version_string())


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
