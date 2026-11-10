# SPDX-License-Identifier: GPL-2.0-or-later
"""An upload to extensions.gnome.org sends what `gnome-extensions upload` sends, says why
the site refused it, and never prints the password or the token."""

import json
import threading
from collections.abc import Generator
from dataclasses import dataclass, field
from email.message import Message
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from tools.ego import main

USER = "owner"
PASSWORD = "pass-word-1"
TOKEN = "tok-en-1"
BUNDLE_BYTES = b"PK\x03\x04 a bundle"


@dataclass
class Sent:
    path: str
    headers: Message
    body: bytes


@dataclass
class FakeSite:
    """What the fake site answers to a login and to an upload, and what it was sent."""

    url: str = ""
    login: tuple[int, object] = (200, {"detail": "Login successful", "token": {"token": TOKEN}})
    upload: tuple[int, object] = (201, {"version": 2, "link": "/extension/9/scroll-zoom/"})
    sent: list[Sent] = field(default_factory=list[Sent])


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> Generator[FakeSite]:
    fake = FakeSite()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (the name http.server calls)
            length = int(self.headers["Content-Length"])
            fake.sent.append(Sent(self.path, self.headers, self.rfile.read(length)))
            routes = {"/api/v1/accounts/login/": fake.login, "/api/v1/extensions": fake.upload}
            status, answer = routes.get(self.path, (404, {"detail": "Not found."}))
            body = json.dumps(answer).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("EGO_URL", fake.url)
    monkeypatch.setenv("EGO_USERNAME", USER)
    monkeypatch.setenv("EGO_PASSWORD", PASSWORD)
    try:
        yield fake
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    path = tmp_path / "scroll-zoom.shell-extension.zip"
    path.write_bytes(BUNDLE_BYTES)
    return path


def parts(sent: Sent) -> dict[str, Message]:
    """The form fields of a multipart upload, by name."""
    head = f"Content-Type: {sent.headers['Content-Type']}\r\n\r\n".encode()
    form = BytesParser(policy=HTTP).parsebytes(head + sent.body)
    assert form.is_multipart(), sent.headers["Content-Type"]
    found: dict[str, Message] = {}
    for part in form.iter_parts():
        name = part.get_param("name", header="content-disposition")
        assert isinstance(name, str)
        found[name] = part
    return found


def test_an_upload_logs_in_then_sends_the_bundle_and_both_statements(
    site: FakeSite, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["upload", str(bundle), "--accept-terms"]) == 0
    assert f"version 2: {site.url}/extension/9/scroll-zoom/" in capsys.readouterr().out
    login, upload = site.sent
    assert login.path == "/api/v1/accounts/login/"
    assert parse_qs(login.body.decode()) == {"login": [USER], "password": [PASSWORD]}
    assert upload.path == "/api/v1/extensions"
    assert upload.headers["Authorization"] == f"Token {TOKEN}"
    fields = parts(upload)
    assert set(fields) == {"source", "shell_license_compliant", "tos_compliant"}
    assert fields["source"].get_filename() == bundle.name
    assert fields["source"].get_content_type() == "application/zip"
    assert fields["source"].get_payload(decode=True) == BUNDLE_BYTES
    assert fields["shell_license_compliant"].get_payload() == "true"
    assert fields["tos_compliant"].get_payload() == "true"


def test_nothing_is_sent_without_accepting_the_terms(
    site: FakeSite, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["upload", str(bundle)]) == 2
    assert not site.sent
    assert "--accept-terms" in capsys.readouterr().err


def test_a_missing_password_sends_nothing(
    site: FakeSite, bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EGO_PASSWORD")
    assert main(["upload", str(bundle), "--accept-terms"]) == 1
    assert not site.sent


def test_a_refused_login_says_why_and_uploads_nothing(
    site: FakeSite, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site.login = (400, {"detail": "Login or password invalid."})
    assert main(["upload", str(bundle), "--accept-terms"]) == 1
    assert [sent.path for sent in site.sent] == ["/api/v1/accounts/login/"]
    assert "Login or password invalid." in capsys.readouterr().err


def test_a_refused_upload_says_why(
    site: FakeSite, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site.upload = (400, {"source": ["An extension with that UUID has already been added"]})
    assert main(["upload", str(bundle), "--accept-terms"]) == 1
    assert "An extension with that UUID has already been added" in capsys.readouterr().err


def test_the_password_and_token_never_reach_the_output(
    site: FakeSite, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["upload", str(bundle), "--accept-terms"])
    site.upload = (500, {"detail": "Server error."})
    main(["upload", str(bundle), "--accept-terms"])
    out = capsys.readouterr()
    for secret in (PASSWORD, TOKEN):
        assert secret not in out.out + out.err
