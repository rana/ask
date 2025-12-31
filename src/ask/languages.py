"""Language detection for code files."""

from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "go": "go",
    "rs": "rust",
    "py": "python",
    "sh": "bash",
    "bash": "bash",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "xml": "xml",
    "ini": "ini",
    "env": "bash",
    "md": "markdown",
    "mdx": "markdown",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "less": "less",
    "sql": "sql",
    "proto": "protobuf",
}

FILENAMES: dict[str, str] = {
    "Makefile": "makefile",
    "makefile": "makefile",
    "GNUmakefile": "makefile",
    "Justfile": "just",
    "justfile": "just",
    "Dockerfile": "dockerfile",
    "dockerfile": "dockerfile",
    "Containerfile": "dockerfile",
    "docker-compose.yml": "yaml",
    "docker-compose.yaml": "yaml",
    ".gitignore": "gitignore",
    ".gitattributes": "gitattributes",
    ".dockerignore": "dockerignore",
    ".env": "bash",
    ".env.local": "bash",
    ".env.example": "bash",
    ".envrc": "bash",
    ".bashrc": "bash",
    ".zshrc": "zsh",
    ".profile": "bash",
    "CMakeLists.txt": "cmake",
    "Cargo.toml": "toml",
    "Cargo.lock": "toml",
    "go.mod": "gomod",
    "go.sum": "gosum",
    "package.json": "json",
    "tsconfig.json": "jsonc",
    "jsconfig.json": "jsonc",
    ".prettierrc": "json",
    ".eslintrc": "json",
    "deno.json": "jsonc",
    "bun.lockb": "text",
    "requirements.txt": "text",
    "pyproject.toml": "toml",
    "Pipfile": "toml",
    "setup.py": "python",
    "setup.cfg": "ini",
}


def language_for(path: str) -> str:
    """Get the language identifier for a file path."""
    # Get filename from path
    filename = path.rsplit("/", 1)[-1] if "/" in path else path

    # Check exact filename match
    if filename in FILENAMES:
        return FILENAMES[filename]

    # Check case-insensitive filename match
    lower_filename = filename.lower()
    for name, lang in FILENAMES.items():
        if name.lower() == lower_filename:
            return lang

    # Get extension
    if "." not in filename or filename.startswith("."):
        return "text"

    ext = filename.rsplit(".", 1)[-1].lower()
    return LANGUAGES.get(ext, ext)
