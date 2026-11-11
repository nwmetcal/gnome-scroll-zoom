# SPDX-License-Identifier: GPL-2.0-or-later
"""A pull request's Intent section, whether it declares what the branch touches, and whether
the tags its release commands make are the one the release workflow takes.

    python -m tools.intent --body FILE [--base origin/main]

The Intent section, from .github/PULL_REQUEST_TEMPLATE.md, names the requirements the change
makes true, the ones it touches without making them newly true, and when it is done. A branch
touches a requirement when it changes its feature or its steps.

A tag that git tag, git push, or gh release create makes or publishes, as an owner's release
steps do, must be the one the release workflow takes: v followed by the extension's
version-name. Each command is read as a shell reads it, with its own options, wherever it
stands in the description: telling code from prose as GitHub does takes a Markdown parser, and
a tag such a command makes is wrong anywhere.
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
# HTML tags, such as <code>, which hide no command but would join one to its words.
HTML = re.compile(r"<[^<>\n]*>")
# A quote's marks at a line's start, so a command a backslash carries on reads the next
# line's words, not its marks.
QUOTED = re.compile(r"^[ \t]*(?:>[ \t]?)+", re.M)
# A release command: git, with any -C or -c before its subcommand, then tag or push; or gh
# release create. A letter, digit, or hyphen just before it, or anything but a space or a line
# break after it, makes it part of other words, as prose's "git push," is.
RELEASE = re.compile(
    r"(?<![A-Za-z0-9-])(?:git(?:\s+-[Cc]\s+\S+)*\s+(tag|push)|gh\s+release\s+(create))"
    r"(?=[ \t]|\\?\n|$)"
)
# A command's words, up to a line break that no backslash carries on, a backtick, ;, &, or |.
ARGS = re.compile(r"(?:\\\n|[^\n`;&|])*")
WORD = re.compile(r"""(["'])(.*?)\1|(\S+)""")
OPENS = "'\"\u2018\u2019\u201c\u201d*_~([{<"
CLOSES = "'\"\u2018\u2019\u201c\u201d*_~)]}>"
# A word ending in one of these ends the command, as a clause ends in prose.
CLAUSE = ",.;:!?"
# With whatever a tag name carries after the numbers, such as -rc1 or +1, which the release
# workflow refuses as it does any other tag.
TAG = re.compile(r"v\d+\.\d+\.\d+\S*")


@dataclass(frozen=True)
class Grammar:
    """What a release command's options mean, as its own help gives them."""

    values: frozenset[str]
    """The options that take a value, the word after them or after their =."""
    reads: frozenset[str]
    """The options that make it delete, list, or verify a tag instead of making one."""
    remote: bool
    """Whether its first argument is a remote, and the rest what it publishes."""


GRAMMARS = {
    "tag": Grammar(
        frozenset({"-m", "--message", "-F", "--file", "-u", "--local-user", "--cleanup"})
        | frozenset({"--trailer", "--sort", "--format", "--contains", "--no-contains"})
        | frozenset({"--points-at", "--merged", "--no-merged"}),
        frozenset({"-d", "--delete", "-l", "--list", "-v", "--verify", "-n", "--contains"})
        | frozenset({"--no-contains", "--points-at", "--merged", "--no-merged"}),
        remote=False,
    ),
    "push": Grammar(
        frozenset({"-o", "--push-option", "--repo", "--receive-pack", "--exec"}),
        frozenset({"-d", "--delete"}),
        remote=True,
    ),
    "create": Grammar(
        frozenset({"-n", "--notes", "-F", "--notes-file", "-t", "--title", "--target", "-R"})
        | frozenset({"--repo", "--discussion-category", "--notes-start-tag"}),
        frozenset(),
        remote=False,
    ),
}


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


def _words(args: str) -> list[tuple[str, bool]]:
    """A command's words as a shell reads them, each with whether it was quoted, up to a
    comment or the first bare word that ends a clause; quotes, emphasis, and brackets around a
    bare word, and a clause's punctuation after it, are not part of it."""
    words: list[tuple[str, bool]] = []
    for word in WORD.finditer(args):
        if word.group(3) is None:
            words.append((word.group(2), True))
            continue
        if word.group(3).startswith("#"):
            break
        core, ends = word.group(3).lstrip(OPENS), False
        while core and core[-1] in CLOSES + CLAUSE:
            ends = ends or core[-1] in CLAUSE
            core = core[:-1]
        words.append((core, False))
        if ends:
            break
    return words


def _made(grammar: Grammar, words: list[tuple[str, bool]]) -> list[str]:
    """The arguments that are what the command makes or publishes, or none when it only
    deletes, lists, or verifies."""
    arguments: list[str] = []
    taking = ended = False
    for word, quoted in words:
        if taking:
            taking = False
        elif ended or quoted or not word.startswith("-") or word == "-":
            arguments.append(word)
        elif word == "--":
            ended = True
        elif word.startswith("--"):
            name = word.split("=", 1)[0]
            if name in grammar.reads:
                return []
            taking = name in grammar.values and "=" not in word
        else:
            for index, letter in enumerate(word[1:], start=1):
                if f"-{letter}" in grammar.reads:
                    return []
                if f"-{letter}" in grammar.values:
                    taking = index == len(word) - 1
                    break
    return arguments[1:] if grammar.remote else arguments[:1]


def _named(argument: str) -> list[str]:
    """The tags an argument names: a tag, or refs/tags/ or tags/ and one, alone or on either
    side of a refspec. A refspec with no source deletes what it names."""
    if argument.startswith(":"):
        return []
    sides = [side.removeprefix("+") for side in argument.split(":")]
    names = [side.removeprefix("refs/").removeprefix("tags/") for side in sides]
    return [name for name in names if TAG.fullmatch(name)]


def release_tags(body: str) -> set[str]:
    """The tags the description's release commands make or publish: git tag and gh release
    create the first argument that is not an option or an option's value, and git push each
    argument after its remote. A command is read wherever it stands, to the end of its line
    unless a backslash carries it on, a backtick, ;, &, or |."""
    text = QUOTED.sub("", HTML.sub(" ", body))
    found: set[str] = set()
    for command in RELEASE.finditer(text):
        args = ARGS.match(text, command.end())
        grammar = GRAMMARS[command.group(1) or command.group(2)]
        words = _words(args.group(0).replace("\\\n", " ") if args else "")
        found.update(tag for argument in _made(grammar, words) for tag in _named(argument))
    return found


def tag_problems(body: str, version: str) -> list[str]:
    """Each tag the description's release commands name that the release workflow refuses."""
    named = release_tags(body)
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
