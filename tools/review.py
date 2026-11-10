# SPDX-License-Identifier: GPL-2.0-or-later
"""Reviews in the loop: the brief a reviewer is given, and the form a review must take.

    python -m tools.review brief --body FILE [--base origin/main]   what a reviewer is given
    python -m tools.review check FILE                               whether a review is well formed

The form is in review/README.md.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from tools.intent import parsed, section

ROOT = Path(__file__).resolve().parent.parent
LENSES = ROOT / "review" / "lenses"
FIRST = re.compile(r"^## Review: ([a-z]+)$")
HEAD = re.compile(r"^Head: [0-9a-f]{40}$")
VERDICT = re.compile(r"^Verdict: (clean|findings)$")
JUDGMENT = re.compile(r"^(\d+)\. (met|unmet: .+|out of scope: .+)$")
FINDING = re.compile(r"^(\d+)\. (blocking|note): .+$")
EVIDENCE = re.compile(r"^ {3}Evidence: .+$")
# Paths whose change is documentation only: no code for the correctness lens to break.
DOCS = re.compile(r"^(?:docs/.*|review/.*|README\.md|AGENTS\.md|LICENSE)$")


def lenses() -> list[str]:
    """The lenses review/lenses/ defines."""
    return sorted(path.stem for path in LENSES.glob("*.md"))


def needed(paths: list[str], names_requirements: bool) -> list[str]:
    """The lenses a change to these paths needs."""
    wanted = ["rules"]
    if any(not DOCS.match(path) for path in paths):
        wanted.append("correctness")
    reqs = any(p.startswith(("requirements/", "tests/requirements/")) for p in paths)
    if names_requirements or reqs:
        wanted.append("requirements")
    return wanted


def problems(review: str) -> list[str]:
    """Every way the review breaks the form; empty when it is well formed."""
    lines = review.strip("\n").splitlines()
    if not lines:
        return ["the review is empty"]
    first = FIRST.match(lines[0])
    if first is None:
        return [f"the first line must be '## Review: <lens>', not {lines[0]!r}"]
    found: list[str] = []
    if first.group(1) not in lenses():
        found.append(f"no lens is named {first.group(1)!r}; review/lenses/ has {lenses()}")
    if sum(1 for line in lines if HEAD.match(line)) != 1:
        found.append("the review needs one 'Head: <40-digit commit>' line")
    verdicts = [m.group(1) for line in lines if (m := VERDICT.match(line))]
    if len(verdicts) != 1:
        return [*found, "the review needs one 'Verdict: clean' or 'Verdict: findings' line"]
    judged = _numbered(lines, "Done when:", JUDGMENT, found)
    blocking = _findings(lines, found)
    unmet = any(text.startswith("unmet") for text in judged)
    clean = not blocking and not unmet
    if (verdicts[0] == "clean") != clean:
        found.append(f"the verdict is {verdicts[0]!r} but the review says otherwise")
    return found


def _numbered(lines: list[str], heading: str, item: re.Pattern[str], found: list[str]) -> list[str]:
    if heading not in lines:
        found.append(f"the review needs a '{heading}' list")
        return []
    texts: list[str] = []
    for line in lines[lines.index(heading) + 1 :]:
        if not line.strip():
            if texts:
                break
            continue
        match = item.match(line)
        if match is None:
            break
        if int(match.group(1)) != len(texts) + 1:
            found.append(f"'{heading}' is not numbered 1, 2, 3, ...: {line!r}")
        texts.append(match.group(2))
    if not texts:
        found.append(f"the '{heading}' list is empty")
    return texts


def _findings(lines: list[str], found: list[str]) -> int:
    """Check the findings and return how many block."""
    if "Findings: none" in lines:
        return 0
    if "Findings:" not in lines:
        found.append("the review needs 'Findings: none' or a 'Findings:' list")
        return 0
    start = lines.index("Findings:") + 1
    blocking = 0
    number = 0
    for index in range(start, len(lines)):
        match = FINDING.match(lines[index])
        if match is None:
            if lines[index].strip() and not EVIDENCE.match(lines[index]):
                break
            continue
        number += 1
        if int(match.group(1)) != number:
            found.append(f"'Findings:' is not numbered 1, 2, 3, ...: {lines[index]!r}")
        if match.group(2) == "blocking":
            blocking += 1
            following = lines[index + 1] if index + 1 < len(lines) else ""
            if not EVIDENCE.match(following):
                found.append(f"blocking finding {number} has no indented 'Evidence:' line")
    if number == 0:
        found.append("the 'Findings:' list is empty; write 'Findings: none'")
    return blocking


def brief(body: str, base: str) -> str:
    """What a reviewer is given: the head, what changed, the lenses, and the intent."""
    head = _git("rev-parse", "HEAD").strip()
    status = _git("diff", "--name-status", "--no-renames", f"{base}...HEAD")
    paths = [line.split("\t", 1)[1] for line in status.splitlines() if "\t" in line]
    intent = parsed(body)
    names = not isinstance(intent, str) and bool(intent.requirements | intent.touches)
    done = [] if isinstance(intent, str) else list(intent.done_when)
    parts = [
        f"Head: {head}",
        f"Lenses: {', '.join(needed(paths, names))}",
        "",
        "Changed:",
        status.rstrip() or "(nothing)",
        "",
        "Intent:",
        (section(body, "Intent") or "(none)").strip(),
        "",
        "Done when:",
        *[f"{n}. {line}" for n, line in enumerate(done, start=1)],
    ]
    return "\n".join(parts) + "\n"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main(argv: list[str]) -> int:
    """Run a subcommand; 1 when a review is malformed."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for_brief = commands.add_parser("brief")
    for_brief.add_argument("--body", type=Path, required=True)
    for_brief.add_argument("--base", default="origin/main")
    for_check = commands.add_parser("check")
    for_check.add_argument("review", type=Path)
    args = parser.parse_args(argv)
    if args.command == "brief":
        print(brief(Path(args.body).read_text(), str(args.base)), end="")
        return 0
    found = problems(Path(args.review).read_text())
    for problem in found:
        print(f"review: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
