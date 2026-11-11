# SPDX-License-Identifier: GPL-2.0-or-later
"""A pull request's Intent section, and whether it declares what the branch touches.

    python -m tools.intent --body FILE [--base origin/main]

The Intent section, from .github/PULL_REQUEST_TEMPLATE.md, names the requirements the change
makes true, the ones it touches without making them newly true, and when it is done. A branch
touches a requirement when it changes its feature or its steps.

A release tag the description names in code, as an owner's release steps do, is the one the
release workflow takes: v followed by the extension's version-name.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ID = re.compile(r"SZ-\d{3}")
FEATURE = re.compile(r"^requirements/(SZ-\d{3})[-.]")
STEPS = re.compile(r"^tests/requirements/test_sz_(\d{3})\.py$")
PLACEHOLDER = "what is true once this is done"
METADATA = Path(__file__).resolve().parent.parent / "scroll-zoom@nhicc" / "metadata.json"
# Fenced blocks first, so an inline span never starts inside one; a list item indents its fence.
CODE = re.compile(r"^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1|`[^`\n]+`", re.M | re.S)
# With a suffix such as -rc1, which the release workflow refuses as it does any other tag.
TAG = re.compile(r"(?<![\w.])v\d+\.\d+\.\d+(?:-[\w.]+)?(?![\w.])")


@dataclass(frozen=True)
class Intent:
    requirements: frozenset[str]
    touches: frozenset[str]
    done_when: tuple[str, ...]


def section(body: str, title: str) -> str | None:
    """The text under a '## title' heading, up to the next '## ' heading."""
    match = re.search(rf"^## {re.escape(title)}[ \t]*$(.*?)(?=^## |\Z)", body, re.M | re.S)
    return match.group(1) if match else None


def _ids(line: str) -> frozenset[str] | str:
    value = line.split(":", 1)[1].strip()
    if value.lower() == "none":
        return frozenset()
    ids = [part.strip() for part in value.split(",")]
    bad = [part for part in ids if not ID.fullmatch(part)]
    if bad:
        return f"not a requirement id: {', '.join(bad)}"
    return frozenset(ids)


def parsed(body: str) -> Intent | str:
    """The intent, or why it cannot be read."""
    text = section(body, "Intent")
    if text is None:
        return "no ## Intent section"
    lines = [line.strip() for line in text.splitlines()]
    declared: dict[str, frozenset[str]] = {}
    for key in ("Requirements", "Touches"):
        found = [line for line in lines if line.startswith(f"{key}:")]
        if len(found) != 1:
            return f"the Intent section needs one '{key}:' line"
        ids = _ids(found[0])
        if isinstance(ids, str):
            return f"{key}: {ids}"
        declared[key] = ids
    if "Done when:" not in lines:
        return "no Done when: list"
    after = lines[lines.index("Done when:") + 1 :]
    done = tuple(line[2:].strip() for line in after if line.startswith("- "))
    if not done or any(line == PLACEHOLDER for line in done):
        return "no Done when: list"
    return Intent(declared["Requirements"], declared["Touches"], done)


def touched(paths: list[str]) -> frozenset[str]:
    """The requirements whose features or steps are among the changed paths."""
    ids: set[str] = set()
    for path in paths:
        if match := FEATURE.match(path):
            ids.add(match.group(1))
        elif match := STEPS.match(path):
            ids.add(f"SZ-{match.group(1)}")
    return frozenset(ids)


def changed_paths(base: str) -> list[str]:
    """Every path the branch changes since it left base; a rename counts as both names."""
    out = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def problems(intent: Intent, paths: list[str]) -> list[str]:
    """What the intent leaves undeclared."""
    declared = intent.requirements | intent.touches
    return [
        f"{rid}: touched but declared under neither Requirements nor Touches"
        for rid in sorted(touched(paths) - declared)
    ]


def version_name() -> str:
    """The extension's version-name, which the release workflow holds a tag to."""
    return str(json.loads(METADATA.read_text())["version-name"])


def tag_problems(body: str, version: str) -> list[str]:
    """Each release tag the description names in code that the release workflow would refuse."""
    named = {tag.group(0) for code in CODE.finditer(body) for tag in TAG.finditer(code.group(0))}
    return [
        f"names the tag {tag}, but version-name is {version}: "
        f"the release workflow takes only v{version}"
        for tag in sorted(named)
        if tag != f"v{version}"
    ]


def main(argv: list[str]) -> int:
    """Print each problem and return 1, or return 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", type=Path, required=True, help="the description, as a file")
    parser.add_argument("--base", default="origin/main", help="the branch it merges into")
    args = parser.parse_args(argv)
    body = Path(args.body).read_text()
    intent = parsed(body)
    if isinstance(intent, str):
        print(f"intent: {intent}", file=sys.stderr)
        return 1
    found = problems(intent, changed_paths(str(args.base))) + tag_problems(body, version_name())
    for problem in found:
        print(f"intent: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
