# SPDX-License-Identifier: GPL-2.0-or-later
"""Upload a bundle to extensions.gnome.org for review, as `gnome-extensions upload` does.

    EGO_USERNAME=... EGO_PASSWORD=... python -m tools.ego upload FILE --accept-terms

It logs in with the account's name and password, then sends the bundle with the two
statements the site's upload page asks for. GNOME Shell's own tool
(subprojects/extensions-tool/src/command-upload.c) sends the same requests. EGO_URL points it
at another site, as the tests do.
"""

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "https://extensions.gnome.org"
TIMEOUT_S = 60
# What --accept-terms agrees to, in the site's own words (ExtensionUploadSerializer).
STATEMENTS = (
    "shell_license_compliant: in any controversial case regarding the compatibility of the"
    " extension's license with the GNOME Shell's license, the extension may be used by any"
    " GNOME Shell user under the terms of the license used by GNOME Shell",
    "tos_compliant: a staff of extensions.gnome.org website may remove, modify or reassign"
    " maintainership of the extension",
)


type Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]


def member(value: Json, key: str) -> Json:
    """value[key] when value is an object that has it, else None."""
    return value.get(key) if isinstance(value, dict) else None


class UploadError(RuntimeError):
    """The site refused a request, and says why."""


def _send(request: urllib.request.Request) -> tuple[int, Json]:
    """The status and the JSON answer; a refusal raises UploadError with the site's reason."""
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            answer: Json = json.loads(response.read() or b"null")
            return response.status, answer
    except urllib.error.HTTPError as refused:
        raise UploadError(f"{request.full_url}: {_reason(refused)}") from refused


def _reason(refused: urllib.error.HTTPError) -> str:
    body = refused.read()
    try:
        answer: Json = json.loads(body)
    except ValueError:
        return f"{refused.code} {refused.reason}"
    if (detail := member(answer, "detail")) is not None:
        return f"{refused.code} {detail}"
    return f"{refused.code} {json.dumps(answer)}"


def login(site: str, user: str, password: str) -> str:
    """A token for the account."""
    form = urllib.parse.urlencode({"login": user, "password": password}).encode()
    _, answer = _send(urllib.request.Request(f"{site}/api/v1/accounts/login/", data=form))
    token = member(member(answer, "token"), "token")
    if not isinstance(token, str):
        raise UploadError(f"{site}: the login answered without a token")
    return token


def upload(site: str, token: str, bundle: Path) -> Json:
    """Send the bundle for review with both statements; the site's answer."""
    boundary = secrets.token_hex(16)
    fields = [
        (f'name="source"; filename="{bundle.name}"', "application/zip", bundle.read_bytes()),
        ('name="shell_license_compliant"', None, b"true"),
        ('name="tos_compliant"', None, b"true"),
    ]
    body = b""
    for disposition, kind, value in fields:
        body += f"--{boundary}\r\nContent-Disposition: form-data; {disposition}\r\n".encode()
        body += f"Content-Type: {kind}\r\n".encode() if kind else b""
        body += b"\r\n" + value + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{site}/api/v1/extensions",
        data=body,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    status, answer = _send(request)
    if status != 201:
        raise UploadError(f"{site}: the upload answered {status}, not 201 Created")
    return answer


def main(argv: list[str]) -> int:
    """Upload the bundle; 1 when the site refuses, 2 when the terms are not accepted."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for_upload = commands.add_parser("upload")
    for_upload.add_argument("bundle", type=Path)
    for_upload.add_argument(
        "--accept-terms",
        action="store_true",
        help="make the two statements the upload page asks for, in the account's name",
    )
    args = parser.parse_args(argv)
    if not args.accept_terms:
        print(
            "ego: uploading makes these statements; pass --accept-terms to make them:",
            file=sys.stderr,
        )
        for statement in STATEMENTS:
            print(f"  - {statement}", file=sys.stderr)
        return 2
    user = os.environ.get("EGO_USERNAME", "")
    password = os.environ.get("EGO_PASSWORD", "")
    if not user or not password:
        print("ego: set EGO_USERNAME and EGO_PASSWORD to the account's", file=sys.stderr)
        return 1
    site = os.environ.get("EGO_URL", SITE).rstrip("/")
    try:
        answer = upload(site, login(site, user, password), Path(args.bundle))
    except UploadError as refused:
        print(f"ego: {refused}", file=sys.stderr)
        return 1
    # The site answers with the version it numbered and the extension's page.
    version, link = member(answer, "version"), member(answer, "link")
    print(f"ego: uploaded {args.bundle} for review as version {version}: {site}{link}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
