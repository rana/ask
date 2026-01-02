# ask

AI conversations through Markdown files.

Develop software in markdown, reference files with `[​[path]​]`, run `ask`, and AI responds directly in your file. The session file is the conversation—editable, searchable, and under your control.

## Installation

### Binary (Recommended)

Download the latest release for your platform from [GitHub Releases](https://github.com/rana/ask/releases):

```bash
# Linux (amd64)
curl -LO https://github.com/rana/ask/releases/latest/download/ask-VERSION-linux-amd64.tar.xz
tar -xJf ask-VERSION-linux-amd64.tar.xz
sudo mv ask /usr/local/bin/

# macOS (Apple Silicon)
curl -LO https://github.com/rana/ask/releases/latest/download/ask-VERSION-darwin-arm64.tar.xz
tar -xJf ask-VERSION-darwin-arm64.tar.xz
sudo mv ask /usr/local/bin/

# Windows (PowerShell)
Invoke-WebRequest -Uri https://github.com/rana/ask/releases/latest/download/ask-VERSION-windows-amd64.zip -OutFile ask.zip
Expand-Archive ask.zip -DestinationPath .
# Add to PATH or move to a directory in PATH
```

Verify installation:

```bash
ask --version
```

### From Source

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/rana/ask.git
cd ask
uv sync
uv run ask --version
```

## Quick Start

```bash
# Initialize a session
ask init

# Add your question to session.md, then run
ask

# AI responds directly in your file
# Apply any code changes from AI response
ask apply

# Run checks (lint, type check, tests)
ask check
```

## Usage

```
ask [command] [options]

Commands:
  chat       Continue the conversation (default)
  init       Initialize a new session file
  apply      Apply files and commands from AI response
  check      Run verification checks
  refresh    Re-expand marked references in place
  cfg        View or update configuration
  version    Show version information
  help       Show help for a command

Global Options:
  -V, --version    Show version and exit

Run 'ask help <command>' for command-specific options.
```

## Session Format

Sessions are markdown files with turn headers:

```markdown
# [1] Human

Reflect on the design and implementation?

[​[src/example.py]​]

# [2] AI

I find a few aspects particularly...

# [3] Human

_
```

- `# [N] Human` / `# [N] AI` — Turn headers
- `[​[path]​]` — Reference a file (expanded automatically)
- `[​[dir/]​]` — Reference directory (non-recursive)
- `[​[dir/**/]​]` — Reference directory (recursive)
- `[​[https://...]​]` — Reference URL content
- `_` — Input marker (where you write next)

## Configuration

Configuration is stored in `~/.ask/config.jsonc`:

```bash
ask cfg                    # Show current config
ask cfg model sonnet       # Set model
ask cfg temperature 0.7    # Set temperature
ask cfg reset              # Reset to defaults
```

## Requirements

- AWS credentials configured (`aws configure`)
- Access to Amazon Bedrock Claude models
- Cross-region inference enabled in AWS account
