"""
Croofx CLI — v0.0.1
====================
Entry point for the `croofx analyze` command.

Usage:
    croofx analyze [PATH] [--json]

    PATH     Repository root to scan (default: current directory)
    --json   Output raw JSON instead of human-readable summary
"""

import argparse
import json
import sys
from pathlib import Path

from croofx.scanner import scan_repo, scan_repo_json


# ---------------------------------------------------------------------------
# Human-readable output formatter
# ---------------------------------------------------------------------------

def format_human(result: dict) -> str:
    """
    Formats scan result for human reading.
    This output is NOT guaranteed deterministic (uses formatting helpers).
    Use --json for deterministic output.
    """
    lines = []
    lines.append(f"\n  Croofx — Repo Analysis")
    lines.append(f"  {'─' * 40}")
    lines.append(f"  Root       : {result['repo_root']}")
    lines.append(f"  Files      : {result['file_count']}")
    lines.append("")

    # Language distribution
    if result["languages"]:
        lines.append("  Languages detected:")
        for lang, count in result["languages"].items():
            lines.append(f"    {lang:<20} {count} file(s)")
    else:
        lines.append("  No recognized languages detected.")

    lines.append("")

    # Dependency files
    if result["dependency_files"]:
        lines.append("  Dependency files found:")
        for dep in result["dependency_files"]:
            lines.append(f"    {dep}")
    else:
        lines.append("  No dependency files found.")

    lines.append("")
    lines.append(f"  Files scanned:")
    for f in result["files"][:20]:  # cap at 20 for readability
        lang_tag = f"[{f['language']}]" if f["language"] else "[unknown]"
        lines.append(f"    {lang_tag:<16} {f['path']}")

    if result["file_count"] > 20:
        lines.append(f"    ... and {result['file_count'] - 20} more files")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_analyze(args):
    """Runs the deterministic repo scanner."""
    path = args.path or "."

    # Validate path
    target = Path(path).resolve()
    if not target.exists():
        print(f"  Error: path does not exist: {target}", file=sys.stderr)
        sys.exit(1)
    if not target.is_dir():
        print(f"  Error: path is not a directory: {target}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # Deterministic JSON output — byte-for-byte stable
        print(scan_repo_json(str(target)))
    else:
        # Human-readable summary
        from croofx.scanner import scan_repo
        result = scan_repo(str(target))
        print(format_human(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="croofx",
        description="Croofx — Deterministic AI Execution Control Layer",
    )
    subparsers = parser.add_subparsers(dest="command")

    # `croofx analyze`
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Scan repository deterministically. Does not enforce or apply anything.",
    )
    analyze_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository root (default: current directory)",
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
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
