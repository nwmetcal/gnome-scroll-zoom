# SPDX-License-Identifier: GPL-2.0-or-later
"""The bundle `make zip` builds is one extensions.gnome.org's review takes, by the rules of
its guidelines a file check can see: https://gjs.guide/extensions/review-guidelines/."""

import json
import re
import subprocess
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
# Each way to add a main loop source, and the ways to remove the one kept in a member. The
# guidelines ask that a source be removed even when it would end on its own.
SOURCES = (
    (
        r"\bGLib\.(?:timeout_add|timeout_add_seconds|idle_add)(?:_once)?\(",
        ("GLib.source_remove({})", "GLib.Source.remove({})"),
    ),
    (r"\bglobal\.compositor\.get_laters\(\)\.add\(", ("get_laters().remove({})",)),
    (r"\b(?:setTimeout|setInterval)\(", ("clearTimeout({})", "clearInterval({})")),
)
KEYBINDINGS = {"addKeybinding": "removeKeybinding", "add_keybinding": "remove_keybinding"}
# The forms undone() reads. Any other call that connects a signal, adds a main loop source, or
# binds a key fails the check until it reads that form too, so no form slips by unread.
SIGNAL_FORMS = {"connect", "connect_after", "connectObject"}
SOURCE_FORMS = {
    f"{name}{once}"
    for name in ("timeout_add", "timeout_add_seconds", "idle_add")
    for once in ("", "_once")
}
KEY_FORMS = {*KEYBINDINGS, "grab_accelerator"}


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
    # Decision 0008: a whole major joins once the @shell scenarios pass on its stable release.
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
    undo it, or without undoing it anywhere in the same file. It reads the file, not which
    method runs when, so an undo anywhere in the file counts."""
    flat = re.sub(r"\s+", "", text)
    found: list[str] = []
    signal = r"\.(connect(?:_after)?)\("
    kept = {
        m.end(): (m.group(1), m.group(2))
        for m in re.finditer(rf"(this\.\w+)\s*=\s*([\w.()]+?)\s*{signal}", text)
    }
    for m in re.finditer(signal, text):
        if m.end() not in kept:
            found.append(f"a signal whose id is not kept: {line_of(text, m.start())}")
    for member, receiver in kept.values():
        if f"{receiver}.disconnect({member})" not in flat:
            found.append(f"{receiver} is never disconnected from {member}")
    for m in re.finditer(r"([\w.()]+?)\s*\.connectObject\(", text):
        if f"{m.group(1)}.disconnectObject(this)" not in flat:
            found.append(f"{m.group(1)} is never disconnected: {line_of(text, m.start())}")
    for adds, removes in SOURCES:
        for m in re.finditer(rf"(?:(this\.\w+)\s*=\s*)?{adds}", text):
            member = m.group(1)
            if member is None or not any(r.format(member) in flat for r in removes):
                found.append(f"a main loop source never removed: {line_of(text, m.start())}")
    grabs = {
        m.end(): (m.group(1), m.group(2))
        for m in re.finditer(r"(this\.\w+)\s*=\s*([\w.()]+?)\s*\.grab_accelerator\(", text)
    }
    for m in re.finditer(r"\.grab_accelerator\(", text):
        if m.end() not in grabs:
            found.append(f"a key grab whose action is not kept: {line_of(text, m.start())}")
    for member, receiver in grabs.values():
        if f"{receiver}.ungrab_accelerator({member})" not in flat:
            found.append(f"{receiver} never ungrabs {member}")
    found += unread(text)
    for adds, removes in KEYBINDINGS.items():
        read = {
            m.start(2): m
            for m in re.finditer(rf"([\w.()]+?)\s*\.({adds})\(\s*([^,()]+?)\s*,", text)
        }
        for m in re.finditer(rf"\.({adds})\(", text):
            named = read.get(m.start(1))
            if named is None:
                found.append(f"a keybinding this check cannot read: {line_of(text, m.start())}")
            elif re.sub(r"\s+", "", f"{named[1]}.{removes}({named[3]})") not in flat:
                found.append(f"the keybinding {named[3]} is never removed")
    return found


def unread(text: str) -> list[str]:
    """Each call that connects, adds a source, or binds a key in a form undone() does not read."""
    found: list[str] = []
    for m in re.finditer(r"\.([A-Za-z]\w*)\(", text):
        name, lower = m.group(1), m.group(1).lower()
        if "connect" in lower and not lower.startswith("disconnect") and name not in SIGNAL_FORMS:
            found.append(f"a signal this check cannot read: {line_of(text, m.start())}")
        bind = lower.startswith(("add", "grab")) and (
            "keybinding" in lower or "accelerator" in lower
        )
        if bind and name not in KEY_FORMS:
            found.append(f"a key binding this check cannot read: {line_of(text, m.start())}")
    for m in re.finditer(r"\b(\w+_add\w*|\w+_source_new\w*|attach)\(", text):
        if m.group(1) not in SOURCE_FORMS:
            found.append(f"a main loop source this check cannot read: {line_of(text, m.start())}")
    return found


def line_of(text: str, offset: int) -> str:
    number = text.count("\n", 0, offset) + 1
    return f"line {number}: {text.splitlines()[number - 1].strip()}"


def test_disable_undoes_every_signal_source_and_keybinding() -> None:
    found = [
        f"{name}: {problem}"
        for name in loaded("extension.js")
        for problem in undone((EXTENSION / name).read_text())
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
    }
    for code, problem in left.items():
        assert any(problem in found for found in undone(code)), (code, undone(code))
    clean = """
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
    assert undone(clean) == []
