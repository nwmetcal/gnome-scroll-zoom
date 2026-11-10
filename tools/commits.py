# SPDX-License-Identifier: GPL-2.0-or-later
"""The commit message rules in AGENTS.md.

python -m tools.commits --message FILE    one message, from the commit-msg hook
python -m tools.commits --range A..B      every commit in a range, from CI
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
TITLE = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9-]+\))?: [a-z0-9]")
WIDTH = 72
# Attribution trailers, tool and model names, and words that sell instead of saying.
BANNED = re.compile(
    r"co-authored-by|signed-off-by|generated with|\bclaude\b|\bchatgpt\b|\bcopilot\b|\bgpt-?\d"
    r"|\bopenai\b|\banthropic\b|\bgemini\b|\bllm\b|\bai-generated\b"
    r"|\bseamless(?:ly)?\b|\brobust\b|\bleverag\w*|\bcomprehensive\b|\bblazing\b|\bcutting-edge\b",
    re.IGNORECASE,
)


def problems(message: str) -> list[str]:
    """Every rule the message breaks; empty when it passes."""
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ["the message is empty"]
    title, *body = lines
    found = _title(title) + _body(body)
    if "`" in message or "**" in message:
        found.append("the message carries markdown")
    found += [f"the message uses a banned word: {m.group(0)!r}" for m in BANNED.finditer(message)]
    return found


def _title(title: str) -> list[str]:
    found: list[str] = []
    if not TITLE.match(title):
        found.append(f"the title is not 'type(scope): description' in lowercase: {title!r}")
    if title.endswith("."):
        found.append("the title ends with a period")
    if len(title) > WIDTH:
        found.append(f"the title is over {WIDTH} characters")
    return found


def _body(body: list[str]) -> list[str]:
    if not body:
        return []
    found: list[str] = []
    if body[0].strip():
        found.append("a blank line must separate the title from the body")
    for line in body[1:]:
        if line.strip() and not line.startswith(("- ", "  ")):
            found.append(
                f"a body line is neither a '- ' bullet nor its indented continuation: {line!r}"
            )
        if len(line) > WIDTH:
            found.append(f"a body line is over {WIDTH} characters: {line!r}")
    return found


def messages(commit_range: str) -> list[tuple[str, str]]:
    """(sha, message) for each commit in the range, oldest first."""
    out = subprocess.run(
        ["git", "log", "--reverse", "--format=%H%x00%B%x01", commit_range],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    pairs: list[tuple[str, str]] = []
    for entry in out.split("\x01"):
        if entry.strip():
            sha, text = entry.strip().split("\x00", 1)
            pairs.append((sha, text))
    return pairs


def main(argv: list[str]) -> int:
    """Print each problem and return 1, or return 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--message", type=Path, help="a file holding one commit message")
    which.add_argument("--range", help="a git range, such as origin/main..HEAD")
    args = parser.parse_args(argv)
    if args.message is not None:
        checked = [("this commit", Path(args.message).read_text())]
    else:
        checked = messages(str(args.range))
    failed = False
    for name, text in checked:
        for problem in problems(text):
            print(f"{name[:12]}: {problem}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
