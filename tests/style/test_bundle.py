# SPDX-License-Identifier: GPL-2.0-or-later
"""The bundle `make zip` builds is one extensions.gnome.org's review takes, by the rules of
its guidelines a file check can see: https://gjs.guide/extensions/review-guidelines/."""

import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from typing import cast

from tests.paths import EXTENSION, ROOT

METADATA: dict[str, object] = json.loads((EXTENSION / "metadata.json").read_text())
# The keys the guidelines and GNOME Shell read. `version` is the site's own: it writes it into
# every bundle it serves, and GNOME's updater compares it.
KEYS = {
    "uuid",
    "name",
    "description",
    "shell-version",
    "url",
    "settings-schema",
    "gettext-domain",
    "version-name",
    "session-modes",
    "donations",
}
REQUIRED = {"uuid", "name", "description", "shell-version", "url"}
# The site's own checks: validate_uuid, version_name_validator, and DonationUrl.Type in its
# models.py, and the guidelines' table of session modes.
UUID = re.compile(r"[-a-zA-Z0-9._]+@[-a-zA-Z0-9._]+")
VERSION_NAME = re.compile(r"[a-zA-Z0-9 .]{1,16}")
SESSION_MODES = {"user", "unlock-dialog"}
DONATIONS = {
    "buymeacoffee",
    "custom",
    "github",
    "kofi",
    "liberapay",
    "opencollective",
    "patreon",
    "paypal",
}
RELATIVE_IMPORT = re.compile(r"""^import\b[^;]*?\bfrom\s+['"]\./([\w.-]+\.js)['"]""", re.M | re.S)
GI_IMPORT = re.compile(r"""['"]gi://(\w+)|\bimports\.gi\.(\w+)|\{([^{}]*)\}\s*=\s*imports\.gi\b""")
DEPRECATED = re.compile(r"\bimports\.(?:byteArray|lang|mainloop)\b|\brun_dispose\(")
SHELL_ONLY = {"Clutter", "Meta", "St", "Shell"}
GTK_ONLY = {"Gdk", "Gtk", "Adw"}
# JavaScript allows space around a member's dot and before a call's parenthesis.
DOT = r"\s*\.\s*"
OPEN = r"\s*\("
KEYBINDINGS = {"addKeybinding": "removeKeybinding", "add_keybinding": "remove_keybinding"}
# undone() reads a call as plain code writes it, and marks where it read each one. A word that
# connects a signal, adds a main loop source, or binds a key anywhere else fails the check, as
# do the other forms it knows: a string name, .call, .apply, ?., and a held laters name. A
# name spelled to hide it from a text check, such as an escape in a string or a joined string,
# is left to review. gjs's own parser checks the scanner each part of this relies on.
GLIB_SOURCES = ("timeout_add", "timeout_add_seconds", "idle_add")


def latest_stable_major(today: date) -> int:
    """The newest GNOME Shell major counted as released by today: 40 from March 2021, and
    one more from the first of each March and September, as latest_stable_shell_major in the
    site's analyzer counts them. Each .0 comes out in the middle of its month, so this counts
    it about two weeks early."""
    months = (today.year - 2021) * 12 + today.month - 3
    return 40 + max(0, months) // 6


def metadata_problems(metadata: dict[str, object], today: date) -> list[str]:
    """Every way metadata.json breaks the site's rules; empty when it keeps them."""
    found: list[str] = []
    keys = set(metadata)
    if extra := sorted(keys - KEYS):
        found.append(f"keys the site does not take: {extra}")
    if missing := sorted(REQUIRED - keys):
        found.append(f"keys the site needs: {missing}")
    uuid = metadata.get("uuid")
    if not isinstance(uuid, str) or not UUID.fullmatch(uuid) or re.search(r"[.@]gnome\.org$", uuid):
        found.append(f"not a uuid the site takes: {uuid!r}")
    url = metadata.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        found.append(f"url is where people report problems: {url!r}")
    name = metadata.get("version-name", "1")
    if not isinstance(name, str) or not VERSION_NAME.fullmatch(name.strip(".")):
        found.append(f"not a version-name the site takes: {name!r}")
    found += _shell_version_problems(metadata.get("shell-version"), today)
    if "session-modes" in metadata:
        modes = metadata["session-modes"]
        listed = cast("list[object]", modes) if isinstance(modes, list) else []
        if not listed or not set(listed) <= SESSION_MODES or set(listed) == {"user"}:
            found.append(
                f"session-modes is dropped for user alone, else of {sorted(SESSION_MODES)}"
            )
    if "donations" in metadata:
        found += _donation_problems(metadata["donations"])
    return found


def _shell_version_problems(versions: object, today: date) -> list[str]:
    # Decision 0009: a whole major joins once the @shell scenarios pass on its stable release.
    if not isinstance(versions, list) or not versions:
        return ["shell-version lists the majors it runs on"]
    latest = latest_stable_major(today)
    return [
        f"shell-version {version!r}: list a released major such as '{latest}', never a"
        " development release or a future one"
        for version in cast("list[object]", versions)
        if not isinstance(version, str)
        or not re.fullmatch(r"\d+", version)
        or not 40 <= int(version) <= latest
    ]


def _donation_problems(donations: object) -> list[str]:
    if not isinstance(donations, dict) or not donations:
        return ["donations is dropped when empty, and is an object of the site's kinds"]
    found: list[str] = []
    for kind, value in cast("dict[str, object]", donations).items():
        values = cast("list[object]", value) if isinstance(value, list) else [value]
        if kind not in DONATIONS:
            found.append(f"donations {kind!r} is not one of {sorted(DONATIONS)}")
        if not 1 <= len(values) <= 3 or not all(isinstance(v, str) for v in values):
            found.append(f"donations {kind!r} holds one to three links")
        elif kind == "custom" and not all(re.fullmatch(r"https?://\S+", str(v)) for v in values):
            found.append("donations 'custom' holds http or https links, as the site checks")
    return found


def loaded(entry: str) -> list[str]:
    """The file and every module it imports from the extension's folder, in import order."""
    seen: list[str] = []
    pending = [entry]
    while pending:
        name = pending.pop(0)
        if name in seen:
            continue
        seen.append(name)
        pending += RELATIVE_IMPORT.findall((EXTENSION / name).read_text())
    return seen


def schema() -> tuple[str, str, str]:
    """The settings schema's file name, id, and path."""
    files = sorted((EXTENSION / "schemas").glob("*.gschema.xml"))
    assert len(files) == 1, f"one schema in schemas/, not {[f.name for f in files]}"
    node = ET.parse(files[0]).getroot().find("schema")
    assert node is not None, f"{files[0].name} has no <schema>"
    return files[0].name, node.get("id", ""), node.get("path", "")


def libraries(text: str) -> set[str]:
    """The GObject libraries a module imports, as gi:// or through the older imports.gi."""
    found: set[str] = set()
    for url, member, destructured in GI_IMPORT.findall(text):
        found |= {url, member} | {n.split(":")[0].strip() for n in destructured.split(",")}
    return found - {""}


def test_the_bundle_holds_only_what_the_extension_loads(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    subprocess.run(
        ["make", "-s", "zip", f"BUNDLE={bundle}"], cwd=ROOT, check=True, capture_output=True
    )
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    wanted = {
        "metadata.json",
        *loaded("extension.js"),
        *loaded("prefs.js"),
        f"schemas/{schema()[0]}",
    }
    assert names == wanted, f"extra: {sorted(names - wanted)}, missing: {sorted(wanted - names)}"


def test_metadata_is_what_the_site_takes() -> None:
    assert metadata_problems(METADATA, date.today()) == []
    assert METADATA["uuid"] == EXTENSION.name, "the uuid names the extension's folder"


def test_the_metadata_check_finds_what_the_site_refuses() -> None:
    today = date(2026, 11, 10)
    assert latest_stable_major(today) == 51
    assert latest_stable_major(date(2027, 3, 1)) == 52
    good: dict[str, object] = {
        "uuid": "a@b",
        "name": "A",
        "description": "A.",
        "shell-version": ["50", "51"],
        "url": "https://example.org/a",
    }
    assert metadata_problems(good, today) == []
    refused: list[dict[str, object]] = [
        {"version": 3},
        {"uuid": "a@extensions.gnome.org"},
        {"url": None},
        {"version-name": "1.0.0-beta"},
        {"shell-version": ["52"]},
        {"shell-version": ["51.beta"]},
        {"shell-version": ["3.38"]},
        {"shell-version": []},
        {"session-modes": ["user"]},
        {"session-modes": ["lock-screen", "unlock-dialog"]},
        {"donations": {"bitcoin": "x"}},
        {"donations": {"github": ["a", "b", "c", "d"]}},
        {"donations": {}},
        {"donations": {"custom": "ftp://example.org/give"}},
        {"donations": {"custom": "give me money"}},
    ]
    for change in refused:
        assert metadata_problems(good | change, today), change
    assert metadata_problems(good | {"session-modes": ["user", "unlock-dialog"]}, today) == []
    assert metadata_problems(good | {"donations": {"github": "a"}}, today) == []
    assert metadata_problems(good | {"donations": {"custom": "https://a.org/give"}}, today) == []


def test_the_schema_is_under_gnome_shell_extensions() -> None:
    filename, schema_id, path = schema()
    assert schema_id.startswith("org.gnome.shell.extensions."), schema_id
    assert path.startswith("/org/gnome/shell/extensions/"), path
    assert filename == f"{schema_id}.gschema.xml", filename
    assert METADATA.get("settings-schema") == schema_id


def test_each_process_imports_only_its_own_libraries() -> None:
    for entry, refused in (("extension.js", GTK_ONLY), ("prefs.js", SHELL_ONLY)):
        for name in loaded(entry):
            text = (EXTENSION / name).read_text()
            wrong = sorted(libraries(text) & refused)
            assert not wrong, f"{name}, loaded by {entry}, imports {wrong}"
            assert not DEPRECATED.search(text), f"{name}: {DEPRECATED.search(text)}"


def test_the_library_check_reads_each_way_to_import() -> None:
    text = (
        "import Gtk from 'gi://Gtk';\nconst Adw = imports.gi.Adw;\nconst {Gdk, St: S} = imports.gi;"
    )
    assert libraries(text) == {"Gtk", "Adw", "Gdk", "St"}
    lazy = "class A {\n    enable() {\n        const {Gtk} = imports.gi;\n    }\n}"
    assert libraries(lazy) == {"Gtk"}


def undone(text: str) -> list[str]:
    """What the shell side connects, adds, or binds without keeping what disable() needs to
    undo it, or without undoing it anywhere in the same file, and each place that does so in
    a form it does not read. It reads the file, not which method runs when, so an undo
    anywhere in the file's code counts, though not one written in a string."""
    code = code_only(text)
    # An undo is looked for in code: a string that holds a call is text, not an undo.
    flat = re.sub(r"\s+", "", without_calls_in_strings(text, code))
    found: list[str] = []
    read: set[int] = set()
    for call, undo, what, never in (
        (
            rf"{DOT}(connect(?:_after)?){OPEN}",
            "disconnect",
            "a signal whose id",
            "is never disconnected from",
        ),
        (
            rf"{DOT}(grab_accelerator){OPEN}",
            "ungrab_accelerator",
            "a key grab whose action",
            "never ungrabs",
        ),
    ):
        found += _kept_and_undone(text, code, flat, read, call, undo, what, never)
    for m in re.finditer(rf"([\w.()]+?){DOT}(connectObject){OPEN}", code):
        read.add(m.start(2))
        owner = re.sub(r"\s+", "", (arguments(code, m.end() - 1) or [""])[-1])
        if f"{m.group(1)}.disconnectObject({owner})" not in flat:
            found.append(f"{m.group(1)} is never disconnected: {line_of(text, m.start())}")
    patterns, also_read, held = sources(code)
    read |= also_read
    for adds, removes in patterns:
        for m in re.finditer(rf"(?:(?P<member>this\.\w+)\s*=\s*)?{adds}", code):
            read |= {m.start(group) for group in ("name", "laters") if m.groupdict().get(group)}
            member = m.group("member")
            if member is None or not any(r.format(member) in flat for r in removes):
                found.append(f"a main loop source never removed: {line_of(text, m.start())}")
    for adds, removes in KEYBINDINGS.items():
        named = {
            m.start(2): m
            for m in re.finditer(rf"([\w.()]+?){DOT}({adds}){OPEN}([^,()]+?)\s*,", code)
        }
        for m in re.finditer(rf"{DOT}({adds}){OPEN}", code):
            read.add(m.start(1))
            binding = named.get(m.start(1))
            if binding is None:
                found.append(f"a keybinding this check cannot read: {line_of(text, m.start())}")
            elif re.sub(r"\s+", "", f"{binding[1]}.{removes}({binding[3]})") not in flat:
                found.append(f"the keybinding {binding[3]} is never removed")
    return found + unread(text, code, read, held)


def _kept_and_undone(
    text: str, code: str, flat: str, read: set[int], call: str, undo: str, what: str, never: str
) -> list[str]:
    """Each call whose id is not kept in a member, or whose kept id is never undone."""
    found: list[str] = []
    kept = {
        m.end(): (m.group(1), m.group(2))
        for m in re.finditer(rf"(this\.\w+)\s*=\s*([\w.()]+?){call}", code)
    }
    for m in re.finditer(call, code):
        read.add(m.start(1))
        if m.end() not in kept:
            found.append(f"{what} is not kept: {line_of(text, m.start())}")
    for member, receiver in kept.values():
        if f"{receiver}.{undo}({member})" not in flat:
            found.append(f"{receiver} {never} {member}")
    return found


def glib_names(text: str) -> list[str]:
    """GLib, and each other name the file imports it under."""
    names = re.findall(r"""import\s+(\w+)\s+from\s+['"]gi://GLib['"]""", text)
    names += re.findall(r"(\w+)\s*=\s*imports\.gi\.GLib\b", text)
    return sorted({"GLib", *names})


def sources(
    code: str,
) -> tuple[list[tuple[str, tuple[str, ...]]], set[int], dict[str, set[int]]]:
    """Each way the file adds a main loop source, with a group for the word that adds it and
    the ways to remove one kept in a member; where it reads get_laters() outside an add; and
    each name that holds get_laters(), with where it is assigned."""
    found: list[tuple[str, tuple[str, ...]]] = []
    adders = "|".join(GLIB_SOURCES)
    for glib in glib_names(code):
        removes = (f"{glib}.source_remove({{}})", f"{glib}.Source.remove({{}})")
        found.append((rf"\b{glib}{DOT}(?P<name>(?:{adders})(?:_once)?){OPEN}", removes))
    laters = rf"\bglobal{DOT}compositor{DOT}(?P<laters>get_laters){OPEN}\)"
    # A name holds get_laters() itself only when nothing is reached through the call's result.
    # A name held on another object, such as this._state.laters, is not read.
    held = [
        m
        for m in re.finditer(rf"(?<![\w$.])((?:this\.)?\w+)\s*=\s*{laters}(?!\s*[.?\[])", code)
        if not re.search(r"\.\s*$", code[: m.start(1)])
    ]
    names = [m.group(1) for m in held]
    read = {m.start("laters") for m in held}
    read |= {m.start("laters") for m in re.finditer(rf"{laters}{DOT}remove{OPEN}", code)}
    removes = tuple(f"{later}.remove({{}})" for later in ["global.compositor.get_laters()", *names])
    found.append((rf"{laters}{DOT}(?P<name>add){OPEN}", removes))
    for name in names:
        found.append((rf"(?<![\w.]){re.escape(name)}{DOT}(?P<name>add){OPEN}", removes))
    found.append(
        (rf"\b(?P<name>setTimeout|setInterval){OPEN}", ("clearTimeout({})", "clearInterval({})"))
    )
    assigned: dict[str, set[int]] = {}
    for m in held:
        assigned.setdefault(m.group(1), set()).add(m.start(1))
    return found, read, assigned


def arguments(text: str, opening: int) -> list[str]:
    """The top-level arguments of the call whose parenthesis is at opening."""
    depth, quote, start = 0, "", opening + 1
    args: list[str] = []
    for index in range(opening, len(text)):
        char = text[index]
        if quote:
            quote = "" if char == quote and text[index - 1] != "\\" else quote
        elif char in "'\"`":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return [*args, text[start:index].strip()]
        elif char == "," and depth == 1:
            args.append(text[start:index].strip())
            start = index + 1
    return args


# Words that connect a signal, subscribe on D-Bus, or watch or own a bus name, but not the
# words that undo them.
SIGNAL_WORD = re.compile(r"(?<!dis)connect|(?<!un)subscribe|(?<!un)(?:watch|own)_name", re.I)
SOURCE_WORD = re.compile(r"\w+_add\w*|\w+_source_new\w*|attach|setTimeout|setInterval")
# Words that bind a key: a lower-case name, so a type such as Meta.KeyBindingFlags is not one.
KEY_WORD = re.compile(r"(?!remove|get_)(?=[a-z])\w*(?i:keybinding)\w*|grab\w*(?i:accelerator)\w*")


# Words after which a / starts a regex literal rather than a division.
REGEX_AFTER_WORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case",
    "do", "else", "yield", "await",
}  # fmt: skip


def literals(text: str) -> list[tuple[str, int, int]]:
    """Each comment, string, template text, and regex literal in a JavaScript file, as its
    kind and the span of its whole text. A template's ${...} parts are code, and read as code.
    A string, regex, or comment that does not close where JavaScript needs it to is reported
    as "unclosed": the scanner read something code cannot be, so it may hide code."""
    spans: list[tuple[str, int, int]] = []
    templates: list[int] = []
    depth, last, word, index, dotted = 0, "", "", 0, False
    # Where the last literal ended, so a ++ or -- counts only when it is code.
    code_from = 0
    while index < len(text):
        char = text[index]
        if text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            spans.append(("comment", index, end))
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            closed = end >= 0
            end = end + 2 if closed else len(text)
            spans.append(("comment" if closed else "unclosed", index, end))
            index = code_from = end
            continue
        if char in "'\"":
            end = _closing(text, index + 1, char)
            closed = text[end - 1] == char and end - 1 > index
            spans.append(("string" if closed else "unclosed", index, end))
            index, last, word, code_from = end, "a", "", end
            continue
        if char == "`" or (char == "}" and templates and templates[-1] == depth):
            if char == "}":
                templates.pop()
            end = index + 1
            while end < len(text) and text[end] != "`" and not text.startswith("${", end):
                end += 2 if text[end] == "\\" else 1
            if text.startswith("${", end):
                spans.append(("template", index, end + 2))
                templates.append(depth)
                index, last, word, code_from = end + 2, "(", "", end + 2
            else:
                spans.append(("template", index, min(end + 1, len(text))))
                index, last, word, code_from = end + 1, "a", "", end + 1
            continue
        # A / after n++ or n-- is a division: the two characters stand together in code.
        previous = len(text[:index].rstrip()) - 1
        postfix = previous - 1 >= code_from and text[previous - 1 : previous + 1] in ("++", "--")
        keyword = word in REGEX_AFTER_WORDS and not dotted
        if char == "/" and not postfix and (not last or last in "(,=:[!&|?{};+-*%<>~^" or keyword):
            end, closed = _regex_end(text, index + 1)
            spans.append(("regex" if closed else "unclosed", index, end))
            index, last, word, code_from = end, "a", "", end
            continue
        depth += {"{": 1, "}": -1}.get(char, 0)
        if not char.isspace():
            named = char.isalnum() or char in "_$"
            # A word just after a dot is a property's name, such as this._size.in.
            dotted = dotted if word and named else last == "."
            word = word + char if named else ""
            last = char
        index += 1
    return spans


def _closing(text: str, index: int, quote: str) -> int:
    while index < len(text) and text[index] not in (quote, "\n"):
        index += 2 if text[index] == "\\" else 1
    return min(index + 1, len(text))


def _regex_end(text: str, index: int) -> tuple[int, bool]:
    """Where the regex literal whose text starts at index ends, and whether it closed."""
    in_class, closed = False, False
    while index < len(text) and text[index] != "\n":
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "/" and not in_class:
            index, closed = index + 1, True
            break
        in_class = (in_class or char == "[") and char != "]"
        index += 1
    while index < len(text) and text[index].isalpha():
        index += 1
    return index, closed


def without_calls_in_strings(text: str, code: str) -> str:
    """The code with each string or template text that holds a parenthesis blanked."""
    chars = list(code)
    for kind, start, end in literals(text):
        if kind in ("string", "template") and "(" in text[start:end]:
            for index in range(start, end):
                if chars[index] != "\n":
                    chars[index] = " "
    return "".join(chars)


def code_only(text: str, strings: bool = True) -> str:
    """The text with each comment and regex literal blanked, and each string's and template
    text's contents too unless strings, keeping every offset and line where it was."""
    chars = list(text)
    for kind, start, end in literals(text):
        if kind in ("comment", "regex") or not strings:
            for index in range(start, end):
                if chars[index] != "\n":
                    chars[index] = " "
    return "".join(chars)


def unread(text: str, code: str, read: set[int], held: dict[str, set[int]]) -> list[str]:
    """Each place that connects, subscribes, adds a source, or binds a key in a form undone()
    does not read: every such word in code where undone() read none, before .call included,
    and each string that holds such a name alone, as obj['name'] does; each use of a name
    holding get_laters() but its assignment and its .add( and .remove( calls; and each escape
    in a name outside a string, which hides the word."""
    found: list[str] = []
    bare = code_only(text, strings=False)
    words = [(m.start(), m.group(0)) for m in re.finditer(r"(?<![\w$])[A-Za-z$][\w$]*", bare)]
    # A string or a template's text names a call when it holds only that name, as obj['name'].
    for kind, start, end in literals(text):
        inner = text[start + 1 : end - (2 if text.endswith("${", 0, end) else 1)]
        if kind in ("string", "template") and re.fullmatch(r"[A-Za-z$][\w$]*", inner):
            words.append((start + 1, inner))
    # A name that starts with an underscore is a private member: the extension's own, whose
    # code is read where it is written, or GNOME Shell's, such as the magnifier's
    # _connectSignals, which undoes itself and is left to review.
    for offset, word in words:
        if offset in read or not _call_or_property(bare, offset, word):
            continue
        if SIGNAL_WORD.search(word):
            found.append(f"a signal this check cannot read: {line_of(text, offset)}")
        if SOURCE_WORD.fullmatch(word) or word == "get_laters":
            found.append(f"a main loop source this check cannot read: {line_of(text, offset)}")
        if KEY_WORD.fullmatch(word):
            found.append(f"a key binding this check cannot read: {line_of(text, offset)}")
    for name, assigned in held.items():
        for m in re.finditer(rf"(?<![\w$.]){re.escape(name)}(?![\w$])", bare):
            used = re.match(rf"{DOT}(?:add|remove){OPEN}|\s*=(?!=)", bare[m.end() :]) is not None
            if m.start() not in assigned and not used:
                found.append(
                    f"a main loop source this check cannot read: {line_of(text, m.start())}"
                )
    for m in re.finditer(r"\\u", bare):
        found.append(f"a name this check cannot read: {line_of(text, m.start())}")
    for kind, start, _ in literals(text):
        if kind == "unclosed":
            found.append(f"a line this check cannot read: {line_of(text, start)}")
    return found


def _call_or_property(bare: str, offset: int, word: str) -> bool:
    """Whether a word in code is called or reached as a property, so a variable of that name,
    such as keybindings or connected, is not taken for a call. A string name always counts."""
    if bare[offset : offset + len(word)] != word:
        return True
    after = re.match(OPEN, bare[offset + len(word) :]) is not None
    return after or re.search(rf"{DOT}$", bare[max(0, offset - 80) : offset]) is not None


def misread(text: str, nodes: list[list[str | int]] | str) -> list[str]:
    """Each place gjs's parser and this check's scanner disagree on: a string, template, or
    regex the parser starts where the scanner starts none, or code the parser places where
    the scanner sees a literal or a comment. A misread can hide code, so each one fails."""
    if isinstance(nodes, str):
        return [f"a file gjs cannot parse: {nodes}"]
    spans = literals(text)
    starts = {start: kind for kind, start, _ in spans}
    lines = [0, *(index + 1 for index, char in enumerate(text) if char == "\n")]
    found: list[str] = []
    for kind, line, column in nodes:
        offset = lines[int(line) - 1] + int(column) - 1
        if kind != "code":
            # The parser gives a template with no ${...} as a string.
            plain = kind == "string" and text[offset : offset + 1] == "`"
            agrees = starts.get(offset) == ("template" if plain else kind)
        else:
            agrees = not any(start <= offset < end for _, start, end in spans)
        if not agrees:
            found.append(f"a line this check cannot read: {line_of(text, offset)}")
    return found


def parse(sources: list[str]) -> list[list[list[str | int]] | str]:
    """What gjs's parser finds in each source, by tests/style/js_nodes.js."""
    with tempfile.TemporaryDirectory() as folder:
        listed = Path(folder) / "sources.json"
        listed.write_text(json.dumps(sources))
        done = subprocess.run(
            ["gjs", "-m", str(ROOT / "tests" / "style" / "js_nodes.js"), str(listed)],
            capture_output=True,
            text=True,
            check=True,
        )
    found: list[list[list[str | int]] | str] = json.loads(done.stdout)
    return found


def checked(sources: list[str]) -> list[list[str]]:
    """undone() for each source, with each place the scanner misread it."""
    return [undone(s) + misread(s, nodes) for s, nodes in zip(sources, parse(sources), strict=True)]


def line_of(text: str, offset: int) -> str:
    number = text.count("\n", 0, offset) + 1
    return f"line {number}: {text.splitlines()[number - 1].strip()}"


def test_disable_undoes_every_signal_source_and_keybinding() -> None:
    names = loaded("extension.js")
    texts = [(EXTENSION / name).read_text() for name in names]
    found = [
        f"{name}: {problem}"
        for name, problems in zip(names, checked(texts), strict=True)
        for problem in problems
    ]
    assert not found, "\n".join(found)


def test_the_check_finds_what_disable_leaves_behind() -> None:
    left = {
        "this._a.connect('x', f);": "a signal whose id is not kept",
        "this._a.connect_after('x', f);": "a signal whose id is not kept",
        "this._id = this._a.connect('x', f);": "this._a is never disconnected from this._id",
        "this._id = this._a.connect_after('x', f);": "this._a is never disconnected from",
        "this._a.connectObject('x', f, this);": "this._a is never disconnected",
        "GLib.idle_add(0, f);": "a main loop source never removed",
        "this._id = GLib.timeout_add(0, 1, f);": "a main loop source never removed",
        "GLib.idle_add_once(0, f);": "a main loop source never removed",
        "this._id = GLib.timeout_add_seconds_once(0, 1, f);": "a main loop source never",
        "this._id = global.compositor.get_laters().add(0, f);": "a main loop source never",
        "this._id = setTimeout(f, 1);": "a main loop source never removed",
        "Main.wm.addKeybinding('k', s, 0, 0, f);": "the keybinding 'k' is never removed",
        "Main.wm.addKeybinding(KEY, s, 0, 0, f);": "the keybinding KEY is never removed",
        "global.display.add_keybinding('k', s, 0, f);": "the keybinding 'k' is never removed",
        "Main.wm.addKeybinding(this._name(), s, 0, 0, f);": "a keybinding this check cannot",
        "this._a.connect_object('x', f, this);": "a signal this check cannot read",
        "this._id = GObject.signal_connect(global.stage, 'x', f);": "a signal this check cannot",
        "this._id = GObject.signal_connect_after(this._a, 'x', f);": "a signal this check cannot",
        "this._s = GLib.timeout_source_new(100);": "a main loop source this check cannot read",
        "this._s.attach(null);": "a main loop source this check cannot read",
        "this._w = GLib.child_watch_add(0, pid, f);": "a main loop source this check cannot read",
        "global.display.grab_accelerator('<Super>z', 0);": "a key grab whose action is not kept",
        "this._k = global.display.grab_accelerator('<Super>z', 0);": "never ungrabs this._k",
        "global.display.grab_accelerators(keys);": "a key binding this check cannot read",
        "this._id = global.stage.connect ('x', f);": "global.stage is never disconnected from",
        "GLib.timeout_add (0, 1, f);": "a main loop source never removed",
        "Main.wm.addKeybinding ('k', s, 0, 0, f);": "the keybinding 'k' is never removed",
        "const laters = global.compositor.get_laters();\nthis._l = laters.add(0, f);": (
            "a main loop source never removed"
        ),
        "import G from 'gi://GLib';\nthis._id = G.timeout_add(0, 1, f);": (
            "a main loop source never removed"
        ),
        "this._id = X.timeout_add(0, 1, f);": "a main loop source this check cannot read",
        "this._s = GLib.timeout_source_new (100);": "a main loop source this check cannot",
        "Main.wm.setCustomKeybindingHandler('k', 0, f);": "a key binding this check cannot read",
        "Gio.DBus.session.signal_subscribe(null, 'a', 'b', null, null, 0, f);": (
            "a signal this check cannot read"
        ),
        "this._a.connectObject('x', f, this._h);\nthis._a.disconnectObject(this);": (
            "this._a is never disconnected"
        ),
        "Gio.DBus.watch_name(Gio.BusType.SESSION, 'org.example', 0, null, null);": (
            "a signal this check cannot read"
        ),
        "Gio.DBus.session.own_name('org.example', 0, null, null);": "a signal this check cannot",
        "global.stage['connect']('notify::x', f);": "a signal this check cannot read",
        "global.stage.connect.call(global.stage, 'notify::x', f);": "a signal this check cannot",
        "global.stage.connect.apply(global.stage, args);": "a signal this check cannot read",
        "GLib.timeout_add.call(null, 0, 1, f);": "a main loop source this check cannot read",
        "global.stage?.connectObject('notify::width', f, this);": "a signal this check cannot",
        "this._actors[0].connectObject('x', f, this);": "a signal this check cannot read",
        "global.compositor.get_laters ().add(0, f);": "a main loop source never removed",
        "this._l = global . compositor.get_laters().add(0, f);": "a main loop source never",
        "this._l = global.compositor\n    .get_laters()\n    .add(0, f);": "a main loop source",
        "const {compositor} = global;\nthis._l = compositor.get_laters().add(0, f);": (
            "a main loop source this check cannot read"
        ),
        "this._l = global.display.get_compositor().get_laters().add(0, f);": (
            "a main loop source this check cannot read"
        ),
        # A regex literal that holds // or /* is not a comment, and hides no code after it.
        "this._base = p.replace(/\\/*$/, '');\nthis._id = global.stage.connect('x', f);\n/* a */": (
            "global.stage is never disconnected from this._id"
        ),
        "if (/^https?:\\/\\//.test(u)) this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        "x = `${global.stage.connect('x', f)}`;": "a signal whose id is not kept",
        "global.stage[`connect`]('x', f);": "a signal this check cannot read",
        "this._id = global.stage.connect('x', f);\nlog('global.stage.disconnect(this._id)');": (
            "global.stage is never disconnected from this._id"
        ),
        # get_laters() held on another object is not read.
        "o.laters = global.compositor.get_laters();\no.laters.add(0, f);": "this check cannot",
        "this._s.laters = global.compositor.get_laters();\nthis._l = this._s.laters.add(0, f);": (
            "a main loop source this check cannot read"
        ),
        # A regex after a string and a +, or after n++ +, is a regex, not a division.
        "const re = RegExp(a + '|' + /\\d+/.source); this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        "const re = RegExp(a + `|` + /\\d+/.source); this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        "const s = n++ + /\\d+/.source; this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        "const s = a + +/\\d+/.exec(t)[0]; this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        # A regex the scanner takes for a division leaves code it cannot be, and fails.
        "if (ok) /\\d+/.test(s); this._id = global.stage.connect('x', f);": "this check cannot",
        "if (ok) /'/.test(s); this._id = global.stage.connect('x', f);": "this check cannot",
        "if (p) /\\/\\//.test(p); this._id = global.stage.connect('x', f);": "this check cannot",
        # A property named in or of is not the keyword a regex may follow.
        "const r = this._size.in / 2; this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        # allowKeybinding changes the modes a key of GNOME's runs in, until it is set back.
        "Main.wm.allowKeybinding('switch-applications', Shell.ActionMode.ALL);": (
            "a key binding this check cannot read"
        ),
    }
    for (code, problem), found in zip(left.items(), checked(list(left)), strict=True):
        assert any(problem in each for each in found), (code, found)
    clean = """
        // connects the stage, then subscribes; a comment is not a call
        const keybindings = ['a', 'b'];
        const connected = true;
        this._held = global.compositor.get_laters();
        this._heldLater = this._held.add(0, f);
        this._held.remove(this._heldLater);
        this._held = null;
        const action = global.display.get_keybinding_action(0, 0);
        this._enableLaters();
        this._disableLaters();
        const pattern = /connect|\\/\\*/;
        const half = width / 2 / scale;
        const label = `a ${half / 2} b`;
        this._client_id = this._client.connect('notify::connected', f);
        this._client.disconnect(this._client_id);
        Gio.bus_unwatch_name(this._watch);
        this._spacedLater = global.compositor.get_laters ().add(0, f);
        global.compositor.get_laters().remove(this._spacedLater);
        import G from 'gi://GLib';
        const laters = global.compositor.get_laters();
        this._spaced = global.stage.connect ('y', f);
        this._l2 = laters.add(0, f);
        this._g = G.timeout_add(0, 1, f);
        this._b.connectObject('x', f, this._h);
        global.stage.disconnect(this._spaced);
        laters.remove(this._l2);
        G.source_remove(this._g);
        this._b.disconnectObject(this._h);
        this._id = this._a.connect('x', f);
        this._after = this._a.connect_after('y', f);
        this._a.connectObject('x', f, this);
        this._source = GLib.timeout_add(0, 1, f);
        this._once = GLib.idle_add_once(0, f);
        this._later = global.compositor.get_laters().add(0, f);
        this._timer = setTimeout(f, 1);
        Main.wm.addKeybinding('k', s, 0, 0, f);
        Main.wm.addKeybinding(KEY, s, 0, 0, f);
        global.display.add_keybinding('d', s, 0, f);
        this._key = global.display.grab_accelerator('<Super>z', 0);
        this._connectSignals();
        this._attach();
        this._a.disconnect(this._id);
        this._a.disconnect(this._after);
        this._a.disconnectObject(this);
        GLib.Source.remove(this._source);
        GLib.source_remove(this._once);
        global.compositor.get_laters().remove(this._later);
        clearTimeout(this._timer);
        Main.wm.removeKeybinding('k');
        Main.wm.removeKeybinding(KEY);
        global.display.remove_keybinding('d');
        global.display.ungrab_accelerator(this._key);
    """
    assert checked([clean]) == [[]]


# The forms of a call found to slip by, tried on every kind of call the check reads, so what a
# review finds for one kind is tried on all of them.
FAMILIES = (
    ("", "global.stage", "connect"),
    ("", "global.stage", "connect_after"),
    ("", "global.stage", "connectObject"),
    ("", "GLib", "timeout_add"),
    ("", "GLib", "idle_add_once"),
    ("", "Main.wm", "addKeybinding"),
    ("", "global.display", "add_keybinding"),
    ("", "global.display", "grab_accelerator"),
    ("", "GLib", "timeout_add_seconds"),
    ("", "global", "setTimeout"),
    ("", "global", "setInterval"),
    ("", "global.compositor.get_laters()", "add"),
    ("const laters = global.compositor.get_laters();\n", "laters", "add"),
    ("this._laters = global.compositor.get_laters();\n", "this._laters", "add"),
    ("", "Main.wm", "setCustomKeybindingHandler"),
    ("", "Meta", "keybindings_set_custom_handler"),
    ("", "Gio.DBus.session", "signal_subscribe"),
    ("", "Gio.DBus", "watch_name"),
)


def forms(receiver: str, name: str) -> list[str]:
    escaped = f"\\u{ord(name[0]):04x}{name[1:]}"
    return [
        f"{receiver}['{name}'](a, b);",
        f"{receiver}.{name}.call({receiver}, a, b);",
        f"{receiver}.{name}.apply({receiver}, args);",
        f"{receiver}?.{name}(a, b);",
        f"{receiver}.{escaped}(a, b);",
        # A division after n++ or n-- is not a regex, and hides nothing after it.
        f"const h = n++ / 2; {receiver}.{name}(a, b);",
        f"const h = n-- / 2; {receiver}.{name}(a, b);",
    ]


def test_every_form_found_fails_for_every_kind_of_call() -> None:
    sources = [
        before + form for before, receiver, name in FAMILIES for form in forms(receiver, name)
    ]
    missed = [source for source, found in zip(sources, checked(sources), strict=True) if not found]
    assert not missed, "\n".join(missed)
