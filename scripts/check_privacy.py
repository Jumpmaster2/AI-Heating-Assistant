"""Scan files or a git diff for private data before publishing.

The patterns are NOT part of this repository. Keep them in a local file
(one regular expression per line, ``#`` starts a comment) and pass it with
``--patterns`` or the environment variable ``PRIVACY_PATTERNS``.

Examples:
    python scripts/check_privacy.py --patterns ../private-patterns.txt
    python scripts/check_privacy.py --patterns ../private-patterns.txt --diff origin/main..HEAD
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", ".venv-ha", "__pycache__", ".pytest_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pyc"}


def load_patterns(path: Path) -> list[re.Pattern[str]]:
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(line, re.IGNORECASE))
    return patterns


def tracked_files(root: Path) -> list[Path]:
    """Return files that git would publish (tracked or not ignored)."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = []
    for name in out.splitlines():
        path = root / name
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        files.append(path)
    return files


def scan_text(label: str, text: str, patterns: list[re.Pattern[str]]) -> int:
    hits = 0
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.search(line):
                print(f"{label}:{number}: matches /{pattern.pattern}/")
                hits += 1
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns", default=os.environ.get("PRIVACY_PATTERNS"))
    parser.add_argument("--diff", help="git revision range to scan instead of the tree")
    args = parser.parse_args()
    if not args.patterns:
        print("No pattern file given (--patterns or PRIVACY_PATTERNS).")
        return 2
    patterns = load_patterns(Path(args.patterns))
    root = Path(__file__).resolve().parent.parent

    hits = 0
    # File names are published too.
    for path in tracked_files(root):
        hits += scan_text("path", str(path.relative_to(root)), patterns)
    if args.diff:
        diff = subprocess.run(
            ["git", "diff", "--unified=0", args.diff],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
        added = "\n".join(
            line[1:]
            for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        hits += scan_text(f"diff {args.diff}", added, patterns)
        log = subprocess.run(
            ["git", "log", "--format=%an <%ae>%n%B", args.diff],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
        hits += scan_text("commit messages", log, patterns)
    else:
        for path in tracked_files(root):
            text = path.read_text(encoding="utf-8", errors="replace")
            hits += scan_text(str(path.relative_to(root)), text, patterns)

    if hits:
        print(f"\n{hits} possible private data hit(s). Nothing published.")
        return 1
    print("Privacy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
