"""
Croofx v0.0.1 — Deterministic Repo Scanner
==========================================
Core guarantee: For unchanged repository state, this module must produce
byte-for-byte identical output across runs.

No randomness. No AI. No ranking. No timestamps by default.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env",
    "dist", "build", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".tox", ".eggs", "*.egg-info",
    ".croofx",
}

LANGUAGE_MAP = {
    # Python
    ".py": "python",
    # JavaScript / TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Java
    ".java": "java",
    # C / C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    # Ruby
    ".rb": "ruby",
    # Shell
    ".sh": "shell",
    ".bash": "shell",
    # YAML / JSON / TOML
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    # Markdown / Docs
    ".md": "markdown",
    ".rst": "rst",
    # Dockerfile
    "Dockerfile": "dockerfile",
    ".dockerfile": "dockerfile",
    # Makefile
    "Makefile": "makefile",
    ".mk": "makefile",
}

DEPENDENCY_FILES = {
    "requirements.txt", "requirements-dev.txt", "setup.py", "setup.cfg",
    "pyproject.toml", "Pipfile", "Pipfile.lock",           # Python
    "package.json", "package-lock.json", "yarn.lock",      # Node
    "go.mod", "go.sum",                                     # Go
    "Cargo.toml", "Cargo.lock",                            # Rust
    "pom.xml", "build.gradle", "build.gradle.kts",         # Java
    "Gemfile", "Gemfile.lock",                             # Ruby
    "composer.json", "composer.lock",                      # PHP
}


# ---------------------------------------------------------------------------
# Core Scanner
# ---------------------------------------------------------------------------

class DeterministicScanner:
    """
    Scans a repository deterministically.

    Design constraints (non-negotiable):
    - File lists are always sorted (POSIX-normalized paths, lexicographic)
    - Language keys are always sorted
    - SHA256 used for all hashing
    - Line endings normalized before hashing
    - No timestamps in default output
    - JSON output always uses sorted keys
    """

    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _should_ignore(self, path: Path) -> bool:
        """Returns True if this path should be excluded from scanning."""
        for part in path.parts:
            if part in IGNORE_DIRS:
                return True
        return False

    def _normalize_path(self, path: Path) -> str:
        """
        Returns a POSIX-style path relative to repo root.
        Guarantees consistent separators across OS.
        """
        return path.relative_to(self.root).as_posix()

    def _detect_language(self, path: Path) -> Optional[str]:
        """
        Detects language by file extension or exact filename.
        Returns None if unrecognized.
        """
        # Check exact filename first (e.g., Dockerfile, Makefile)
        if path.name in LANGUAGE_MAP:
            return LANGUAGE_MAP[path.name]
        # Then check extension
        return LANGUAGE_MAP.get(path.suffix.lower())

    def _hash_file(self, path: Path) -> str:
        """
        Computes SHA256 of file content.
        Normalizes line endings to LF before hashing
        to ensure cross-platform determinism.
        """
        try:
            raw = path.read_bytes()
            # Normalize CRLF → LF
            normalized = raw.replace(b"\r\n", b"\n")
            return hashlib.sha256(normalized).hexdigest()
        except (OSError, PermissionError):
            return ""

    def _is_dependency_file(self, path: Path) -> bool:
        return path.name in DEPENDENCY_FILES

    def scan(self) -> dict:
        """
        Walks the repository and returns a deterministic scan result.

        Output schema:
        {
            "files": [
                {
                    "path": "src/main.py",       # POSIX, relative
                    "language": "python",
                    "hash": "<sha256>",
                    "size_bytes": 1234
                },
                ...
            ],
            "languages": {
                "python": 3,
                "typescript": 5,
                ...
            },
            "dependency_files": [
                "requirements.txt",
                ...
            ],
            "file_count": 8,
            "repo_root": "/absolute/path/to/repo"
        }

        Determinism guarantees:
        - files sorted by path (lexicographic, POSIX)
        - languages keys sorted
        - dependency_files sorted
        """
        files = []
        languages: dict[str, int] = {}
        dependency_files = []

        # Walk filesystem
        for dirpath, dirnames, filenames in os.walk(self.root):
            current = Path(dirpath)

            # Prune ignored directories IN PLACE (affects os.walk traversal)
            # Sort dirnames for stable traversal order
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in IGNORE_DIRS and not d.startswith(".")
            )

            for filename in sorted(filenames):  # sorted for determinism
                filepath = current / filename

                if self._should_ignore(filepath):
                    continue

                rel_posix = self._normalize_path(filepath)
                language = self._detect_language(filepath)
                file_hash = self._hash_file(filepath)

                try:
                    size = filepath.stat().st_size
                except OSError:
                    size = 0

                entry = {
                    "path": rel_posix,
                    "language": language,
                    "hash": file_hash,
                    "size_bytes": size,
                }
                files.append(entry)

                # Track language distribution
                if language:
                    languages[language] = languages.get(language, 0) + 1

                # Track dependency files
                if self._is_dependency_file(filepath):
                    dependency_files.append(rel_posix)

        # Enforce deterministic ordering on all output arrays
        files.sort(key=lambda f: f["path"])
        dependency_files.sort()

        return {
            "files": files,
            "languages": dict(sorted(languages.items())),   # sorted keys
            "dependency_files": dependency_files,
            "file_count": len(files),
            "repo_root": str(self.root),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_repo(path: str) -> dict:
    """
    Entry point for the scanner module.
    Returns a fully deterministic scan result dict.
    """
    scanner = DeterministicScanner(path)
    return scanner.scan()


def scan_repo_json(path: str, indent: int = 2) -> str:
    """
    Returns the scan result as a deterministic JSON string.
    Keys are always sorted. No timestamps.
    """
    result = scan_repo(path)
    return json.dumps(result, indent=indent, sort_keys=True)
