# SPDX-License-Identifier: GPL-2.0-or-later
"""The bundle `make zip` builds is one extensions.gnome.org's review takes, by the rules of
its guidelines a file check can see: https://gjs.guide/extensions/review-guidelines/."""

import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
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
# The site's own checks: validate_uuid and version_name_validator in its models.py.
UUID = re.compile(r"[-a-zA-Z0-9._]+@[-a-zA-Z0-9._]+")
VERSION_NAME = re.compile(r"[a-zA-Z0-9 .]{1,16}")
RELATIVE_IMPORT = re.compile(r"""^import\b[^;]*?\bfrom\s+['"]\./([\w.-]+\.js)['"]""", re.M | re.S)
GI_IMPORT = re.compile(r"""['"]gi://(\w+)""")
DEPRECATED = re.compile(r"\bimports\.(?:byteArray|lang|mainloop)\b|\brun_dispose\(")
SHELL_ONLY = {"Clutter", "Meta", "St", "Shell"}
# Each way to add a main loop source, and the ways to remove the one kept in a member.
SOURCES = (
    (
        r"\bGLib\.(?:timeout_add|timeout_add_seconds|idle_add)\(",
        ("GLib.source_remove({})", "GLib.Source.remove({})"),
    ),
    (r"\bglobal\.compositor\.get_laters\(\)\.add\(", ("get_laters().remove({})",)),
    (r"\b(?:setTimeout|setInterval)\(", ("clearTimeout({})", "clearInterval({})")),
)
GTK_ONLY = {"Gdk", "Gtk", "Adw"}


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


def test_the_bundle_holds_only_what_the_extension_loads(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    subprocess.run(
        ["make", "-s", "zip", f"ZIP={bundle}"], cwd=ROOT, check=True, capture_output=True
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


def test_metadata_holds_only_what_the_site_takes() -> None:
    keys = set(METADATA)
    assert keys <= KEYS, f"keys the site does not take: {sorted(keys - KEYS)}"
    assert keys >= REQUIRED, f"keys the site needs: {sorted(REQUIRED - keys)}"
    uuid = METADATA["uuid"]
    assert isinstance(uuid, str) and UUID.fullmatch(uuid), f"not a uuid the site takes: {uuid}"
    assert not re.search(r"[.@]gnome\.org$", uuid), "gnome.org is not a namespace to use"
    assert uuid == EXTENSION.name, "the uuid names the extension's folder"
    url = METADATA["url"]
    assert isinstance(url, str) and url.startswith("https://"), "url: where to report problems"
    name = METADATA.get("version-name", "1")
    assert isinstance(name, str) and VERSION_NAME.fullmatch(name.strip(".")), name


def test_shell_version_lists_only_whole_stable_majors() -> None:
    # Decision 0008: a major joins once the @shell scenarios pass on its stable release.
    versions = METADATA["shell-version"]
    assert isinstance(versions, list) and versions, "shell-version lists the majors it runs on"
    for version in cast("list[object]", versions):
        assert isinstance(version, str) and re.fullmatch(r"\d+", version), (
            f"{version!r}: list a whole major such as '50', never a development release"
        )


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
            wrong = sorted(set(GI_IMPORT.findall(text)) & refused)
            assert not wrong, f"{name}, loaded by {entry}, imports {wrong}"
            assert not DEPRECATED.search(text), f"{name}: {DEPRECATED.search(text)}"


def undone(text: str) -> list[str]:
    """What the shell side connects, adds, or binds without keeping what disable() needs to
    undo it, or without undoing it anywhere in the same file."""
    flat = re.sub(r"\s+", "", text)
    found: list[str] = []
    kept = {
        m.end(): (m.group(1), m.group(2))
        for m in re.finditer(r"(this\.\w+)\s*=\s*([\w.()]+?)\s*\.connect\(", text)
    }
    for m in re.finditer(r"\.connect\(", text):
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
    for m in re.finditer(r"Main\.wm\.addKeybinding\(\s*'([\w-]+)'", text):
        if f"Main.wm.removeKeybinding('{m.group(1)}')" not in flat:
            found.append(f"the keybinding {m.group(1)} is never removed")
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
        "this._id = this._a.connect('x', f);": "this._a is never disconnected from this._id",
        "this._a.connectObject('x', f, this);": "this._a is never disconnected",
        "GLib.idle_add(0, f);": "a main loop source never removed",
        "this._id = GLib.timeout_add(0, 1, f);": "a main loop source never removed",
        "this._id = global.compositor.get_laters().add(0, f);": "a main loop source never",
        "this._id = setTimeout(f, 1);": "a main loop source never removed",
        "Main.wm.addKeybinding('k', s, 0, 0, f);": "the keybinding k is never removed",
    }
    for code, problem in left.items():
        assert any(problem in found for found in undone(code)), code
    clean = """
        this._id = this._a.connect('x', f);
        this._a.connectObject('x', f, this);
        this._source = GLib.timeout_add(0, 1, f);
        this._later = global.compositor.get_laters().add(0, f);
        this._timer = setTimeout(f, 1);
        Main.wm.addKeybinding('k', s, 0, 0, f);
        this._a.disconnect(this._id);
        this._a.disconnectObject(this);
        GLib.Source.remove(this._source);
        global.compositor.get_laters().remove(this._later);
        clearTimeout(this._timer);
        Main.wm.removeKeybinding('k');
    """
    assert undone(clean) == []
