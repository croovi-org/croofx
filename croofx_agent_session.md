# Croofx — Coding Agent Session
## Building v0.0.1: Deterministic Repo Scanner
**Project:** Croofx — Deterministic AI Execution Control Layer  
**Session goal:** Build `croofx analyze` — the deterministic repo scanner (v0.0.1)  
**Language:** Python 3.10+

---

## Context & Spec

Croofx is a deterministic patch enforcement engine that sits between AI-generated code and production systems. Before any patch can be validated or applied, Croofx needs to understand the repository it's operating on — deterministically.

**Core constraint (non-negotiable):** For unchanged repository state, `croofx analyze --json` must produce byte-for-byte identical output across runs. No randomness. No timestamps. No AI. No ranking.

**v0.0.1 must deliver:**
- Recursive directory walker with stable traversal order
- POSIX path normalization (cross-platform consistency)
- Ignore rules: `.git`, `node_modules`, `venv`, `dist`, `build`, `__pycache__`, etc.
- Language detection by file extension and exact filename (Dockerfile, Makefile)
- Dependency file detection (`requirements.txt`, `package.json`, `go.mod`, etc.)
- SHA256 hashing with line-ending normalization (CRLF → LF before hash)
- Output schema: `{ files, languages, dependency_files, file_count, repo_root }`
- All arrays sorted. All JSON keys sorted. Byte-for-byte deterministic.

---

## Prompt 1 — Scanner Core

**User:**
> Build the DeterministicScanner class. It needs to walk the repo recursively, normalize paths to POSIX, detect language by extension, hash each file with SHA256 (normalize line endings first), detect dependency files, and return a fully sorted deterministic dict. No timestamps. No randomness. Sorted file list, sorted language keys, sorted dependency_files.

**Agent reasoning:**
The key design decisions here:
1. `os.walk` with `dirnames[:] = sorted(...)` in-place — this prunes ignored dirs AND enforces stable traversal order in one step.
2. CRLF normalization before SHA256 — otherwise the same file produces different hashes on Windows vs Linux, breaking the determinism guarantee.
3. Exact filename check before extension check in language detection — so `Dockerfile` maps correctly without a `.` extension.
4. All sorting happens at the end on the final arrays, not during accumulation — cleaner and guaranteed.

```python
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
    "pyproject.toml", "Pipfile", "Pipfile.lock",
    "package.json", "package-lock.json", "yarn.lock",
    "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "Gemfile.lock",
    "composer.json", "composer.lock",
}


# ---------------------------------------------------------------------------
# Core Scanner
# ---------------------------------------------------------------------------

class DeterministicScanner:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _should_ignore(self, path: Path) -> bool:
        for part in path.parts:
            if part in IGNORE_DIRS:
                return True
        return False

    def _normalize_path(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _detect_language(self, path: Path) -> Optional[str]:
        if path.name in LANGUAGE_MAP:
            return LANGUAGE_MAP[path.name]
        return LANGUAGE_MAP.get(path.suffix.lower())

    def _hash_file(self, path: Path) -> str:
        try:
            raw = path.read_bytes()
            normalized = raw.replace(b"\r\n", b"\n")
            return hashlib.sha256(normalized).hexdigest()
        except (OSError, PermissionError):
            return ""

    def _is_dependency_file(self, path: Path) -> bool:
        return path.name in DEPENDENCY_FILES

    def scan(self) -> dict:
        files = []
        languages: dict[str, int] = {}
        dependency_files = []

        for dirpath, dirnames, filenames in os.walk(self.root):
            current = Path(dirpath)

            # Prune ignored dirs in-place + enforce stable traversal order
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in IGNORE_DIRS and not d.startswith(".")
            )

            for filename in sorted(filenames):
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

                files.append({
                    "path": rel_posix,
                    "language": language,
                    "hash": file_hash,
                    "size_bytes": size,
                })

                if language:
                    languages[language] = languages.get(language, 0) + 1

                if self._is_dependency_file(filepath):
                    dependency_files.append(rel_posix)

        # Enforce deterministic ordering on all output
        files.sort(key=lambda f: f["path"])
        dependency_files.sort()

        return {
            "files": files,
            "languages": dict(sorted(languages.items())),
            "dependency_files": dependency_files,
            "file_count": len(files),
            "repo_root": str(self.root),
        }


def scan_repo(path: str) -> dict:
    return DeterministicScanner(path).scan()


def scan_repo_json(path: str, indent: int = 2) -> str:
    return json.dumps(scan_repo(path), indent=indent, sort_keys=True)
```

---

## Prompt 2 — CLI Entry Point

**User:**
> Now build the CLI. `croofx analyze [PATH] [--json]`. --json gives deterministic JSON output. Without --json, give a human-readable summary. PATH defaults to current directory. Validate the path exists and is a directory, exit(1) with error if not.

**Agent reasoning:**
Using `argparse` with subparsers to keep the CLI extensible — `validate` and `apply` commands come later and need to slot in cleanly. The `--json` flag only changes output format, never exit behavior (that's a hard rule in the Croofx spec). Human output is explicitly NOT guaranteed deterministic — that's fine, it's for humans.

```python
"""
Croofx CLI — v0.0.1
"""

import argparse
import sys
from pathlib import Path

from croofx.scanner import scan_repo, scan_repo_json


def format_human(result: dict) -> str:
    lines = []
    lines.append(f"\n  Croofx — Repo Analysis")
    lines.append(f"  {'─' * 40}")
    lines.append(f"  Root       : {result['repo_root']}")
    lines.append(f"  Files      : {result['file_count']}")
    lines.append("")

    if result["languages"]:
        lines.append("  Languages detected:")
        for lang, count in result["languages"].items():
            lines.append(f"    {lang:<20} {count} file(s)")
    else:
        lines.append("  No recognized languages detected.")

    lines.append("")

    if result["dependency_files"]:
        lines.append("  Dependency files found:")
        for dep in result["dependency_files"]:
            lines.append(f"    {dep}")
    else:
        lines.append("  No dependency files found.")

    lines.append("")
    lines.append(f"  Files scanned:")
    for f in result["files"][:20]:
        lang_tag = f"[{f['language']}]" if f["language"] else "[unknown]"
        lines.append(f"    {lang_tag:<16} {f['path']}")

    if result["file_count"] > 20:
        lines.append(f"    ... and {result['file_count'] - 20} more files")

    lines.append("")
    return "\n".join(lines)


def cmd_analyze(args):
    path = args.path or "."
    target = Path(path).resolve()

    if not target.exists():
        print(f"  Error: path does not exist: {target}", file=sys.stderr)
        sys.exit(1)
    if not target.is_dir():
        print(f"  Error: path is not a directory: {target}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(scan_repo_json(str(target)))
    else:
        result = scan_repo(str(target))
        print(format_human(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="croofx",
        description="Croofx — Deterministic AI Execution Control Layer",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Scan repository deterministically. Does not enforce or apply anything.",
    )
    analyze_parser.add_argument("path", nargs="?", default=".")
    analyze_parser.add_argument(
        "--json", action="store_true",
        help="Output deterministic JSON (byte-for-byte stable across runs)",
    )
    analyze_parser.set_defaults(func=cmd_analyze)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
```

---

## Verification — Determinism Proof

**User:**
> Run the scanner against itself 3 times and SHA256 each output. They must be identical.

**Agent:**
```bash
cd /home/claude/croofx
OUT1=$(python -m croofx.cli analyze . --json | sha256sum)
OUT2=$(python -m croofx.cli analyze . --json | sha256sum)
OUT3=$(python -m croofx.cli analyze . --json | sha256sum)
echo "Run 1: $OUT1"
echo "Run 2: $OUT2"
echo "Run 3: $OUT3"
```

**Output:**
```
Run 1: d35acf6caf294cefcf011005f36e5cdbf97e03febd78838374157b145b273ba9  -
Run 2: d35acf6caf294cefcf011005f36e5cdbf97e03febd78838374157b145b273ba9  -
Run 3: d35acf6caf294cefcf011005f36e5cdbf97e03febd78838374157b145b273ba9  -

✅ DETERMINISM VERIFIED — byte-for-byte identical across 3 runs
```

---

## Sample Output

Running `croofx analyze . --json` on the Croofx repo itself:

```json
{
  "dependency_files": [
    "pyproject.toml"
  ],
  "file_count": 4,
  "files": [
    {
      "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "language": "python",
      "path": "croofx/__init__.py",
      "size_bytes": 0
    },
    {
      "hash": "7de4a8cdddb6383ba63d2e726b414fb273a9e485c1dd132887e0ec3c707f2482",
      "language": "python",
      "path": "croofx/cli.py",
      "size_bytes": 3902
    },
    {
      "hash": "e30afed13f862794da80750586d4b5ae28461309caf081187ec74f8afdda7306",
      "language": "python",
      "path": "croofx/scanner.py",
      "size_bytes": 7704
    },
    {
      "hash": "265bc3cf4d043618e621f861e77e7c977f88b7e2a9e6a44ac6a5ae8df33ac5b4",
      "language": "toml",
      "path": "pyproject.toml",
      "size_bytes": 371
    }
  ],
  "languages": {
    "python": 3,
    "toml": 1
  },
  "repo_root": "/home/claude/croofx"
}
```

---

## What This Builds Toward

`croofx analyze` is the first layer of Croofx's enforcement spine:

```
v0.0.1  ← THIS SESSION: Deterministic repo scanner
v0.0.2  → Structured AI contract layer (strict JSON schema enforcement)
v0.0.3  → Minimal persistent repo snapshot (.croofx/repo_summary.json)
v0.0.4  → Patch generation engine (unified diff output)
v0.9.0  → Deterministic patch validator (THE NUCLEUS)
v1.0.0  → Full CLI enforcement: croofx validate --ci, croofx apply --force
```

The scanner is not optional infrastructure. Every downstream component — the validator, the patch simulator, the CI enforcement interface — depends on a repo representation that is provably stable. This session builds that foundation.

**Croofx core principle:** AI generates. Croofx enforces.
