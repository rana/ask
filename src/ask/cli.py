"""CLI entry point for ask."""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from ask.apply import apply_session, format_applied_block, insert_applied_block
from ask.bedrock import extract_region, find_profile, stream_completion
from ask.check import check_session
from ask.config import ensure_config, get_config_path, load_config, save_config, update_config
from ask.errors import AskError, ConfigError
from ask.output import output
from ask.session import (
    SessionWriter,
    expand_and_save_session,
    read_session,
    turns_to_messages,
    validate_session,
)
from ask.tokens import estimate_tokens
from ask.types import Config, StreamChunk, StreamEnd
from ask.workspace import find_workspace


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new session file."""
    path = args.path or "session.md"

    if path.endswith("/") or path.endswith("\\"):
        path = f"{path}session.md"

    file_path = Path(path)

    if file_path.exists() and file_path.is_dir():
        file_path = file_path / "session.md"

    if file_path.exists():
        output.error(f"{file_path} already exists")
        output.info("Delete it to start fresh")
        return 1

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

    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """Continue the conversation."""
    session_path = args.session or "session.md"

    if not Path(session_path).exists():
        if session_path == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session_path}")
        return 1

    try:
        config = load_config()
        model_type = args.model or config.model

        session = read_session(session_path)

        expanded, file_count = expand_and_save_session(session_path, session)
        if expanded:
            output.success(f"Expanded {file_count} file{'s' if file_count != 1 else ''}")
            session = read_session(session_path)

        validate_session(session)

        profile = find_profile(model_type)
        region = extract_region(profile)

        output.meta([
            ("Model", f"{output.model_name(profile.model_id)} {output.dim(f'({region})')}")
        ])

        messages = turns_to_messages(session.turns)
        input_tokens = estimate_tokens(messages)
        turn_label = "turn" if len(session.turns) == 1 else "turns"

        output.meta([
            ("Input", f"{output.number(input_tokens)} tokens"),
            ("Turns", f"{len(session.turns)} {turn_label}"),
        ])

        if input_tokens > 150000:
            output.blank()
            output.warning("Large input may be slow or hit limits")

        next_turn_number = session.turns[-1].number + 1
        writer = SessionWriter(session_path, next_turn_number)

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

        return 0

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        return 1
    except Exception as e:
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        return 1


def cmd_apply(args: argparse.Namespace) -> int:
    """Apply files and commands from AI response."""
    session_path = args.session or "session.md"

    if not Path(session_path).exists():
        if session_path == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session_path}")
        return 1

    try:
        apply_files = True
        apply_commands = True

        if args.files:
            apply_commands = False
        elif args.commands:
            apply_files = False

        dry_run = args.dry_run

        session_content = Path(session_path).read_text(encoding="utf-8")
        workspace = find_workspace(session_content)

        if dry_run:
            output.info(output.dim("Dry run - no changes will be made"))
            output.blank()

        if workspace:
            output.meta([("Workspace", str(workspace))])

        result = apply_session(
            session_path,
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
                insert_applied_block(session_path, applied_block)
                output.info(output.dim(f"Updated {session_path}"))
            else:
                output.warning("Apply completed with errors")

                applied_block = format_applied_block(result)
                insert_applied_block(session_path, applied_block)
                output.info(output.dim(f"Updated {session_path}"))

        return 0 if result.status == "OK" else 1

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        return 1
    except Exception as e:
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        return 1


def cmd_check(args: argparse.Namespace) -> int:
    """Run verification checks."""
    session_path = args.session or "session.md"

    if not Path(session_path).exists():
        if session_path == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session_path}")
        return 1

    try:
        fix = args.fix

        session_content = Path(session_path).read_text(encoding="utf-8")
        workspace = find_workspace(session_content)

        if workspace:
            output.meta([("Workspace", str(workspace))])

        if fix:
            output.info(output.dim("Running fixes first..."))

        output.blank()
        output.info(output.dim("Running checks..."))

        result = check_session(session_path, fix=fix)

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

        output.info(output.dim(f"Updated {session_path}"))

        return 0 if result.status == "PASS" else 1

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        return 1
    except Exception as e:
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        return 1


def cmd_cfg(args: argparse.Namespace) -> int:
    """View or update configuration."""
    action = args.action
    value = args.value

    try:
        if not action:
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
            output.field("web", "on" if config.web else "off")

            exclude = config.exclude or Config.default_exclude()
            output.field("exclude", f"{len(exclude)} patterns")

            return 0

        if action == "reset":
            save_config(Config())
            output.success("Reset to defaults")
            return 0

        if not value:
            output.error(f"Missing value for '{action}'")
            output.info(f"Usage: ask cfg {action} <value>")
            return 1

        update_config(action, value)
        output.success(f"{action} set to {value}")
        return 0

    except ConfigError as e:
        output.error(e.message)
        if e.help_text:
            output.info(e.help_text)
        return 1
    except Exception as e:
        output.error(str(e))
        return 1


def cmd_help(args: argparse.Namespace) -> int:
    """Show help information."""
    command = args.command

    if command == "init":
        output.blank()
        output.info(f"{output.bold('ask init')} {output.dim('—')} Initialize a new session file")
        output.blank()
        output.info(output.dim("Usage"))
        output.info("  ask init [path]")
        output.blank()
        output.info(output.dim("Arguments"))
        output.info(f"  {output.cyan('path')}  Path for session file (default: session.md)")
        output.blank()
        output.info(output.dim("Examples"))
        output.info("  $ ask init")
        output.info("  $ ask init session-2.md")
        output.info("  $ ask init notes/research.md")
        output.blank()
    elif command == "apply":
        output.blank()
        output.info(
            f"{output.bold('ask apply')} {output.dim('—')} "
            "Apply files and commands from AI response"
        )
        output.blank()
        output.info(output.dim("Usage"))
        output.info("  ask apply [session] [--dry-run] [--files|--commands|--all]")
        output.blank()
        output.info(output.dim("Arguments"))
        output.info(f"  {output.cyan('session')}    Session file (default: session.md)")
        output.info(f"  {output.cyan('--dry-run')}  Preview without writing or executing")
        output.info(f"  {output.cyan('--files')}    Apply only file blocks")
        output.info(f"  {output.cyan('--commands')} Apply only command blocks")
        output.info(f"  {output.cyan('--all')}      Apply both files and commands (default)")
        output.blank()
        output.info(output.dim("Examples"))
        output.info("  $ ask apply")
        output.info("  $ ask apply --dry-run")
        output.info("  $ ask apply --files")
        output.info("  $ ask apply session-2.md --commands")
        output.blank()
    elif command == "check":
        output.blank()
        output.info(
            f"{output.bold('ask check')} {output.dim('—')} "
            "Run verification checks"
        )
        output.blank()
        output.info(output.dim("Usage"))
        output.info("  ask check [session] [--fix]")
        output.blank()
        output.info(output.dim("Arguments"))
        output.info(f"  {output.cyan('session')}  Session file (default: session.md)")
        output.info(f"  {output.cyan('--fix')}    Run auto-fix commands before checking")
        output.blank()
        output.info(output.dim("Examples"))
        output.info("  $ ask check")
        output.info("  $ ask check --fix")
        output.info("  $ ask check session-2.md")
        output.blank()
    elif command == "cfg":
        output.blank()
        output.info(f"{output.bold('ask cfg')} {output.dim('—')} View or update configuration")
        output.blank()
        output.info(output.dim("Usage"))
        output.info("  ask cfg [field] [value]")
        output.blank()
        output.info(output.dim("Config Fields"))
        output.info(f"  {output.cyan('model')}        AI model (opus/sonnet/haiku)")
        output.info(f"  {output.cyan('temperature')}  Response creativity (0.0-1.0)")
        output.info(f"  {output.cyan('tokens')}       Max output tokens (1-200000)")
        output.info(f"  {output.cyan('region')}       Preferred AWS region")
        output.info(f"  {output.cyan('filter')}       Strip comments from files (on/off)")
        output.info(f"  {output.cyan('web')}          Fetch URL references (on/off)")
        output.info(f"  {output.cyan('reset')}        Reset all settings to defaults")
        output.blank()
        output.info(output.dim("Examples"))
        output.info("  $ ask cfg")
        output.info("  $ ask cfg model sonnet")
        output.info("  $ ask cfg temperature 0.7")
        output.info("  $ ask cfg reset")
        output.blank()
    else:
        output.blank()
        output.info(f"{output.bold('ask')} {output.dim('—')} AI conversations through Markdown")
        output.blank()
        output.info(output.dim("Usage"))
        output.info(f"  ask {output.cyan('[command]')} {output.dim('[options]')}")
        output.blank()
        output.info(output.dim("Commands"))
        output.info(f"  {output.cyan('chat')}     Continue the conversation (default)")
        output.info(f"  {output.cyan('init')}     Initialize a new session file")
        output.info(f"  {output.cyan('apply')}    Apply files and commands from AI response")
        output.info(f"  {output.cyan('check')}    Run verification checks")
        output.info(f"  {output.cyan('cfg')}      View or update configuration")
        output.info(f"  {output.cyan('help')}     Show help information")
        output.blank()
        output.info(output.dim("Examples"))
        output.info(f"  {output.dim('$')} ask                     {output.dim('Continue conversation')}")
        output.info(f"  {output.dim('$')} ask init                {output.dim('Start new session')}")
        output.info(f"  {output.dim('$')} ask apply               {output.dim('Apply AI response')}")
        output.info(f"  {output.dim('$')} ask check               {output.dim('Run checks')}")
        output.info(f"  {output.dim('$')} ask check --fix         {output.dim('Fix then check')}")
        output.info(f"  {output.dim('$')} ask -m sonnet           {output.dim('Use specific model')}")
        output.info(f"  {output.dim('$')} ask help check          {output.dim('Command help')}")
        output.blank()
        output.info(f"Run {output.cyan('ask help <command>')} for details")
        output.blank()

    return 0


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ask",
        description="AI conversations through Markdown files",
        add_help=False,
    )

    subparsers = parser.add_subparsers(dest="command")

    chat_parser = subparsers.add_parser("chat", help="Continue the conversation")
    chat_parser.add_argument("session", nargs="?", help="Session file (default: session.md)")
    chat_parser.add_argument("-m", "--model", help="Model to use (opus/sonnet/haiku)")

    init_parser = subparsers.add_parser("init", help="Initialize a new session file")
    init_parser.add_argument("path", nargs="?", help="Path for session file")

    apply_parser = subparsers.add_parser("apply", help="Apply files and commands from AI response")
    apply_parser.add_argument("session", nargs="?", help="Session file (default: session.md)")
    apply_parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    apply_parser.add_argument("--files", action="store_true", help="Apply only file blocks")
    apply_parser.add_argument("--commands", action="store_true", help="Apply only command blocks")
    apply_parser.add_argument(
        "--all", action="store_true", help="Apply both files and commands (default)"
    )

    check_parser = subparsers.add_parser("check", help="Run verification checks")
    check_parser.add_argument("session", nargs="?", help="Session file (default: session.md)")
    check_parser.add_argument("--fix", action="store_true", help="Run auto-fix commands first")

    cfg_parser = subparsers.add_parser("cfg", help="View or update configuration")
    cfg_parser.add_argument("action", nargs="?", help="Config field or 'reset'")
    cfg_parser.add_argument("value", nargs="?", help="Value to set")

    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.add_argument("command", nargs="?", help="Command to get help for")

    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        sys.argv[1] = "help"

    args = sys.argv[1:]
    if not args or args[0].startswith("-") or args[0] not in (
        "chat", "init", "apply", "check", "cfg", "help"
    ):
        args = ["chat"] + args

    parsed = parser.parse_args(args)

    if parsed.command == "init":
        sys.exit(cmd_init(parsed))
    elif parsed.command == "apply":
        sys.exit(cmd_apply(parsed))
    elif parsed.command == "check":
        sys.exit(cmd_check(parsed))
    elif parsed.command == "cfg":
        sys.exit(cmd_cfg(parsed))
    elif parsed.command == "help":
        sys.exit(cmd_help(parsed))
    else:
        sys.exit(cmd_chat(parsed))


if __name__ == "__main__":
    main()
