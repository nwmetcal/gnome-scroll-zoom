# SPDX-License-Identifier: GPL-2.0-or-later
"""The bundle `make zip` builds is one extensions.gnome.org's review takes, by the rules of
its guidelines a file check can see: https://gjs.guide/extensions/review-guidelines/."""

import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
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
KEYBINDINGS = {"addKeybinding": "removeKeybinding", "add_keybinding": "remove_keybinding"}
TIMERS = {"setTimeout": "clearTimeout", "setInterval": "clearInterval"}
GLIB_SOURCES = {
    f"{name}{once}"
    for name in ("timeout_add", "timeout_add_seconds", "idle_add")
    for once in ("", "_once")
}
LATERS = "global.compositor.get_laters()"
# The undo check reads each call as gjs's own parser reads it (tests/style/js_nodes.js). A name
# that connects a signal, adds a main loop source, or binds a key, standing anywhere but in a
# call read here, fails it: through .call, .apply, ?., or a computed name, or taken off its
# object. A name the parser resolves, such as obj['con' + 'nect'], is read as that name.
# Words that connect a signal, subscribe on D-Bus, or watch or own a bus name, but not the
# words that undo them.
SIGNAL_WORD = re.compile(r"(?<!dis)connect|(?<!un)subscribe|(?<!un)(?:watch|own)_name", re.I)
# A string names a signal's method only in a method's own spelling: the word first or after an
# underscore, then nothing, an underscore, or a capital. So 'connect_after', 'connectObject',
# and 'signal_subscribe' are names, and a property or key such as 'Connected' or 'reconnect',
# or a signal called 'connected', is not.
SIGNAL_NAME = re.compile(r"(?:\w+_)?(?:connect|subscribe|(?:watch|own)_name)(?:[A-Z_]\w*)?")
# Names that run code from a string, or load a module while the extension runs: code no
# reading of the bundle's files sees. Every function's constructor is Function.
CODE = {"eval", "Function", "constructor", "import()"}
SOURCE_WORD = re.compile(r"\w+_add\w*|\w+_source_new\w*|attach|setTimeout|setInterval")
# Words that bind a key: a lower-case name, so a type such as Meta.KeyBindingFlags is not one.
KEY_WORD = re.compile(r"(?!remove|get_)(?=[a-z])\w*(?i:keybinding)\w*|grab\w*(?i:accelerator)\w*")

type Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]


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
    made = subprocess.run(
        ["make", "-s", "zip", f"BUNDLE={bundle}"], cwd=ROOT, capture_output=True, text=True
    )
    assert made.returncode == 0, made.stderr
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


@dataclass(frozen=True)
class Call:
    """A call as gjs's parser reads it; see tests/style/js_nodes.js."""

    line: int
    name: str | None
    receiver: str | None
    form: str
    kept: str | None
    args: tuple[str | None, ...]
    use: str | None


@dataclass(frozen=True)
class Read:
    """What gjs's parser reads in one source: its calls, the places names stand, and the
    names that hold global.compositor.get_laters()."""

    calls: tuple[Call, ...]
    names: tuple[tuple[int, str, int | str], ...]
    holds: frozenset[str]
    held: tuple[tuple[int, str, str], ...]
    glib: frozenset[str]


def _read(found: Json) -> Read | str:
    if isinstance(found, str):
        return found
    facts = cast("dict[str, list[list[Json]]]", found)
    calls = tuple(
        Call(
            cast(int, c[0]),
            cast("str | None", c[1]),
            cast("str | None", c[2]),
            cast(str, c[3]),
            cast("str | None", c[4]),
            tuple(cast("list[str | None]", c[5])),
            cast("str | None", c[6]),
        )
        for c in facts["calls"]
    )
    names = tuple(
        (cast(int, n[0]), cast(str, n[1]), cast("int | str", n[2])) for n in facts["names"]
    )
    held = tuple((cast(int, h[0]), cast(str, h[1]), cast(str, h[2])) for h in facts["held"])
    holds = frozenset(cast("list[str]", facts["holds"]))
    return Read(calls, names, holds, held, frozenset(cast("list[str]", facts["glib"])))


def parse(sources: list[str]) -> list[Read | str]:
    """What gjs's parser reads in each source, by tests/style/js_nodes.js, or its error."""
    with tempfile.TemporaryDirectory() as folder:
        listed = Path(folder) / "sources.json"
        listed.write_text(json.dumps(sources))
        command = ["gjs", "-m", str(ROOT / "tests" / "style" / "js_nodes.js"), str(listed)]
        done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"gjs could not read the sources: {done.stderr.strip()}")
    found: list[Json] = json.loads(done.stdout)
    return [_read(each) for each in found]


def checked(sources: list[str]) -> list[list[str]]:
    """undone() for each source, as gjs's parser reads it."""
    return [
        [f"a file gjs cannot parse: {read}"] if isinstance(read, str) else undone(source, read)
        for source, read in zip(sources, parse(sources), strict=True)
    ]


def family(name: str, string: bool = False) -> str | None:
    """What a name connects, adds, or binds, if it is one of those names; a string's name is
    held to a method's spelling."""
    if SIGNAL_NAME.fullmatch(name) if string else SIGNAL_WORD.search(name):
        return "signal"
    if SOURCE_WORD.fullmatch(name) or name == "get_laters":
        return "main loop source"
    if KEY_WORD.fullmatch(name):
        return "key binding"
    return None


def undone(text: str, read: Read) -> list[str]:
    """What the shell side connects, adds, or binds without keeping what disable() needs to
    undo it, or without undoing it anywhere in the same file, and each place a name that
    connects, adds, or binds stands other than in a call read here. It reads the file, not
    which method runs when, so an undo anywhere in the file counts."""
    lines = re.split(r"\r\n|[\n\r  ]", text)

    def at(line: int) -> str:
        return f"line {line}: {lines[line - 1].strip()}"

    undos = {(c.receiver, c.name, c.args[0] if c.args else None) for c in read.calls}
    laters = {LATERS, *read.holds}
    found: list[str] = []
    readable: set[int] = set()
    for index, c in enumerate(read.calls):
        plain = c.form == "dot" and c.receiver is not None
        if plain and c.name in ("connect", "connect_after"):
            readable.add(index)
            if c.kept is None:
                found.append(f"a signal whose id is not kept: {at(c.line)}")
            elif (c.receiver, "disconnect", c.kept) not in undos:
                found.append(f"{c.receiver} is never disconnected from {c.kept}")
        elif plain and c.name == "connectObject":
            readable.add(index)
            owner = c.args[-1] if c.args else None
            if owner is None or (c.receiver, "disconnectObject", owner) not in undos:
                found.append(f"{c.receiver} is never disconnected: {at(c.line)}")
        elif plain and c.name in GLIB_SOURCES and c.receiver in read.glib:
            readable.add(index)
            removes = {(g, "source_remove") for g in read.glib}
            removes |= {(f"{g}.Source", "remove") for g in read.glib}
            if c.kept is None or not any((r, n, c.kept) in undos for r, n in removes):
                found.append(f"a main loop source never removed: {at(c.line)}")
        elif c.name in TIMERS and c.form in ("dot", "bare") and c.receiver is not None:
            readable.add(index)
            clears = {(r, n, c.kept) for r in ("", c.receiver) for n in TIMERS.values()}
            if c.kept is None or not clears & undos:
                found.append(f"a main loop source never removed: {at(c.line)}")
        elif plain and c.name == "add" and c.receiver in laters:
            if c.kept is None or not any((r, "remove", c.kept) in undos for r in laters):
                found.append(f"a main loop source never removed: {at(c.line)}")
        elif plain and c.name == "get_laters" and c.receiver == "global.compositor" and c.use:
            readable.add(index)
        elif plain and c.name in KEYBINDINGS:
            readable.add(index)
            key = c.args[0] if c.args else None
            if key is None:
                found.append(f"a keybinding this check cannot read: {at(c.line)}")
            elif (c.receiver, KEYBINDINGS[c.name], key) not in undos:
                found.append(f"the keybinding {key} is never removed")
        elif plain and c.name == "grab_accelerator":
            readable.add(index)
            if c.kept is None:
                found.append(f"a key grab whose action is not kept: {at(c.line)}")
            elif (c.receiver, "ungrab_accelerator", c.kept) not in undos:
                found.append(f"{c.receiver} never ungrabs {c.kept}")
    # A name that starts with an underscore is a private member: the extension's own, whose
    # code is read where it is written, or GNOME Shell's, such as the magnifier's
    # _connectSignals, which undoes itself and is left to review.
    for line, name, site in read.names:
        if name in CODE and site not in ("declared", "key"):
            found.append(f"code this check cannot read: {at(line)}")
        kind = family(name, string=site == "string")
        if kind and not name.startswith("_") and site != "declared" and site not in readable:
            found.append(f"a {kind} this check cannot read: {at(line)}")
    for line, _, role in read.held:
        if role == "other":
            found.append(f"a main loop source this check cannot read: {at(line)}")
    return found


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
        "Main.wm.addKeybinding(this._name(), s, 0, 0, f);": "the keybinding this._name() is never",
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
        # The parser reads a string name as the name it is.
        "global.stage['connect']('notify::x', f);": "a signal whose id is not kept",
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
        # A regex after if (...) is a regex, and hides nothing after it.
        "if (ok) /\\d+/.test(s); this._id = global.stage.connect('x', f);": "never disconnected",
        "if (ok) /'/.test(s); this._id = global.stage.connect('x', f);": "never disconnected",
        "if (p) /\\/\\//.test(p); this._id = global.stage.connect('x', f);": "never disconnected",
        # A property named in or of is not the keyword a regex may follow.
        "const r = this._size.in / 2; this._id = global.stage.connect('x', f);": (
            "global.stage is never disconnected from this._id"
        ),
        # A division before a comment is a division, and the comment's text is not code.
        "this._id = s.connect('x', f);\nconst x = {} / [] // s.disconnect(this._id)": (
            "s is never disconnected from this._id"
        ),
        "this._id = s.connect('x', f);\nconst x = n++ /* c */ / [] // s.disconnect(this._id)": (
            "s is never disconnected from this._id"
        ),
        # get_laters() held only in a full statement of its own.
        "this._l = (this._laters = global.compositor.get_laters()).add(0, f);": (
            "a main loop source this check cannot read"
        ),
        "const x = this._laters = global.compositor.get_laters();\nthis._l = x.add(0, f);": (
            "a main loop source this check cannot read"
        ),
        # A line break ends a statement only when the next line does not go on with it.
        "const laters = global.compositor.get_laters()\n    ?.add(0, f);": "this check cannot read",
        "this._laters = global.compositor.get_laters()\n    ['add'](0, f);": "never removed",
        # JavaScript ends a line at U+2028 and U+2029 too, and a first #! line is a comment.
        "this._id = s.connect('x', f);\n// a\u2028/*\ns.disconnect(this._id) /* */": "never",
        "#!s.disconnect(this._id)\nthis._id = s.connect('x', f);": "never disconnected",
        # A key is read: a string key as the name it holds, a computed key as code.
        "const {'connect': link} = global.stage;\nthis._id = link.call(global.stage, 'x', f);": (
            "a signal this check cannot read"
        ),
        "({[global.stage.connect('notify::width', f)]: 0});": "a signal whose id is not kept",
        "class A {\n    [GLib.timeout_add(0, 100, f)]() {}\n}": "a main loop source never removed",
        "class A {\n    'connect'() {}\n}": "a signal this check cannot read",
        "({get [global.stage.connect('x', f)]() {}});": "a signal whose id is not kept",
        # A string that holds such a name alone is read as that name.
        "const NAME = 'connect';\nthis._id = global.stage[NAME]('x', f);": "a signal this check",
        "this._id = Reflect.get(global.stage, 'connect').call(global.stage, 'x', f);": (
            "a signal this check cannot read"
        ),
        # get_laters() held on this, as on any other object, is not read, even undone: this goes
        # where no reading of one file follows it, into a function, a constructor, an array,
        # or another module.
        "this._laters = global.compositor.get_laters();\nconst {_laters} = this;\n_laters.add();": (
            "a main loop source this check cannot read"
        ),
        "this._laters = global.compositor.get_laters();\nconst self = this;\nself._laters.add();": (
            "a main loop source this check cannot read"
        ),
        "this._laters = global.compositor.get_laters();\n"
        "this._l = this._laters.add(0, f);\nthis._laters.remove(this._l);": (
            "a main loop source this check cannot read"
        ),
        "this._laters = global.compositor.get_laters();\nschedule(this);\n"
        "function schedule(e) {\n    e._l = e._laters.add(0, f);\n}": (
            "a main loop source this check cannot read"
        ),
        "this._laters = global.compositor.get_laters();\nnew Helper(this);": (
            "a main loop source this check cannot read"
        ),
        "this._laters = global.compositor.get_laters();\nthis._l = [this][0]._laters.add(0, f);": (
            "a main loop source this check cannot read"
        ),
        "this._laters = global.compositor.get_laters();\nconst KEY = '_laters';\n"
        "this._l = this[KEY].add(0, f);": "a main loop source this check cannot read",
        # A name another module can import is reached where this file cannot see.
        "export const laters = global.compositor.get_laters();\n"
        "this._l = laters.add(0, f);\nlaters.remove(this._l);": (
            "a main loop source this check cannot read"
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
        this._broken = global.compositor
            .get_laters()
            .add(0, f);
        global.compositor.get_laters().remove(this._broken);
        const wide = '\U0001d465'; const narrow = 'a';
        const connected = true;
        const on = this._proxy.get_cached_property('Connected');
        const again = this._settings.get_boolean('reconnect');
        this._link = this._client.connect('connected', f);
        this._client.disconnect(this._link);
        const meta = import.meta.url;
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
        # A name taken off its object by a quoted key, and by a computed one.
        f"const {{'{name}': h}} = {receiver};\nh(a, b);",
        f"const {{['{name}']: h}} = {receiver};\nh(a, b);",
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


# Ways to run code from a string, or to load a module while the extension runs: the code they
# run is in no file the check reads. Each fails. Any other way, such as a module gjs's older
# importer loads through imports.<name>, is left to review.
STRING_CODE = "\"global.stage.connect('x', f);\""
RUN_FROM_A_STRING = (
    f"eval({STRING_CODE});",
    f"globalThis.eval({STRING_CODE});",
    f"(0, eval)({STRING_CODE});",
    f"const E = 'eval';\nglobalThis[E]({STRING_CODE});",
    f"new Function({STRING_CODE})();",
    f"Function({STRING_CODE})();",
    f"(function () {{}}).constructor({STRING_CODE})();",
    f"(() => {{}}).constructor({STRING_CODE})();",
    f"const AF = (async () => {{}}).constructor;\nnew AF({STRING_CODE})();",
    f"Object.getPrototypeOf(function* () {{}}).constructor({STRING_CODE});",
    f"this.constructor.constructor({STRING_CODE})();",
    f"[].map.constructor({STRING_CODE})();",
    f"Reflect.get(() => {{}}, 'constructor')({STRING_CODE})();",
    f"const {{constructor: make}} = () => {{}};\nmake({STRING_CODE})();",
    "import('./probe.js');",
)


def test_code_run_from_a_string_fails() -> None:
    sources: list[str] = list(RUN_FROM_A_STRING)
    for source, found in zip(sources, checked(sources), strict=True):
        assert any("code this check cannot read" in each for each in found), (source, found)
    # A class's own constructor() is where it is written, and is read there.
    own = "class A extends B {\n    constructor() {\n        super();\n    }\n}"
    meta = "const here = import.meta.url;"
    assert checked([own, meta]) == [[], []]


# A name called bare rather than on a receiver, and one taken off its object under another.
BARE: tuple[str, ...] = (
    "this._t = setTimeout.call(globalThis, f, 1);",
    "this._t = setTimeout.apply(globalThis, [f, 1]);",
    "this._t = setTimeout?.(f, 1);",
    "this._t = setInterval.call(globalThis, f, 1);",
    "const later = setTimeout;\nthis._t = later(f, 1);",
    "const {timeout_add: later} = GLib;\nthis._t = later(0, 1, f);",
    "const {bus_watch_name: watch} = Gio;\nthis._w = watch(a, b);",
    "const {connect} = global.stage;\nthis._id = connect('x', f);",
    # A name the file declares counts everywhere but at its own declaration.
    "let connect;\n({connect} = global.stage);\nthis._id = connect.call(global.stage, 'x', f);",
    "const connect = 1;\nfunction g(connect) {\n    this._id = connect.call(s, 'x', f);\n}",
    "function a() {\n    const setTimeout = 1;\n    return setTimeout;\n}\nsetTimeout.call(g, f);",
)


def test_a_bare_or_borrowed_name_fails() -> None:
    sources: list[str] = list(BARE)
    missed = [source for source, found in zip(sources, checked(sources), strict=True) if not found]
    assert not missed, "\n".join(missed)


# Names spelled to hide a call from a reading of the text, which gjs's parser reads as the call
# each makes: an escape, a joined string, and a space at a dot. Left undone, each fails.
SPELLED = (
    "global.stage['\\x63onnect']('x', f);",
    "global.stage['\\u{63}onnect']('x', f);",
    "global.stage['con' + 'nect']('x', f);",
    "Main.wm['addKey\\x62inding']('k', s, 0, 0, f);",
    "Main.wm['add' + 'Keybinding']('k', s, 0, 0, f);",
    "this._id = GLib['timeout\\x5fadd'](0, 1, f);",
    "GLib['timeout_' + 'add'](0, 1, f);",
    "this._laters = global.compositor.get_laters();\nthis ._laters['add'](0, () => false);",
)


def test_a_name_spelled_to_hide_a_call_is_read_as_the_call_it_makes() -> None:
    sources: list[str] = list(SPELLED)
    missed = [source for source, found in zip(sources, checked(sources), strict=True) if not found]
    assert not missed, "\n".join(missed)
    undone_then = (
        "this._id = global.stage['\\x63onnect']('x', f);\nglobal.stage.disconnect(this._id);"
    )
    assert checked([undone_then]) == [[]]
