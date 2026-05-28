"""GitHub webhook server: HMAC, ping, push filtering."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parent.parent
DEPLOY = REPO / "services" / "telegram" / "deploy"

# Import from deploy dir (stdlib-only module).
import sys

sys.path.insert(0, str(DEPLOY))
from github_webhook_server import (  # noqa: E402
    should_trigger_sync,
    verify_github_signature,
    WEBHOOK_PATH,
)


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_github_signature_valid():
    secret = "test-secret"
    body = b'{"zen":"test"}'
    assert verify_github_signature(secret, body, _sign(secret, body))


def test_verify_github_signature_invalid():
    assert not verify_github_signature("secret", b"{}", "sha256=deadbeef")


def test_should_trigger_sync_main_only():
    assert not should_trigger_sync("ping", {})
    assert should_trigger_sync(
        "push", {"ref": "refs/heads/main", "repository": {"name": "founders-notes"}}
    )
    assert not should_trigger_sync("push", {"ref": "refs/heads/feature/foo"})
    assert not should_trigger_sync("pull_request", {"ref": "refs/heads/main"})


def test_trigger_sync_background_invokes_script(tmp_path: Path):
    vault = tmp_path
    script = vault / "services" / "telegram" / "deploy" / "sync-and-index.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    script.chmod(0o755)
    log_path = tmp_path / "sync.log"

    from github_webhook_server import trigger_sync_background

    with patch("github_webhook_server.subprocess.Popen") as popen:
        trigger_sync_background(vault, log_path=log_path)
        popen.assert_called_once()
        args, kwargs = popen.call_args
        assert args[0][0] == str(script)
        assert kwargs.get("start_new_session") is True


def test_webhook_handler_ping_and_push():
    import io

    from github_webhook_server import GitHubWebhookHandler
    from http.server import HTTPServer

    secret = "hook-secret"
    vault = REPO
    httpd = HTTPServer(("127.0.0.1", 0), GitHubWebhookHandler)
    httpd.webhook_secret = secret
    httpd.vault_root = vault
    httpd.sync_log_path = Path("/tmp/founders-test-sync.log")

    ping_body = json.dumps({"zen": "test"}).encode("utf-8")

    class FakeConnection:
        def __init__(self, path: str, body: bytes, event: str):
            self.path = path
            self._body = body
            self.headers = {
                "Content-Length": str(len(body)),
                "X-GitHub-Event": event,
                "X-Hub-Signature-256": _sign(secret, body),
            }

        def makefile(self, mode: str, bufsize: int = -1):  # noqa: ARG002
            return io.BytesIO(self._body)

    class RecordingHandler(GitHubWebhookHandler):
        def __init__(self, conn: FakeConnection, client_address, server):
            self.request = conn
            self.client_address = client_address
            self.server = server
            self.headers = conn.headers
            self.path = conn.path
            self.rfile = conn.makefile("rb")
            self.wfile = io.BytesIO()
            self._code = 0

        def send_response(self, code: int, message: str | None = None) -> None:
            self._code = code

        def send_header(self, key: str, value: str) -> None:
            pass

        def end_headers(self) -> None:
            pass

        def send_error(self, code: int, message: str | None = None) -> None:
            self._code = code

    handler = RecordingHandler(FakeConnection(WEBHOOK_PATH, ping_body, "ping"), ("127.0.0.1", 12345), httpd)
    handler.do_POST()
    assert handler._code == 200

    push_body = json.dumps({"ref": "refs/heads/main"}).encode("utf-8")
    handler2 = RecordingHandler(
        FakeConnection(WEBHOOK_PATH, push_body, "push"), ("127.0.0.1", 12345), httpd
    )
    with patch("github_webhook_server.trigger_sync_background") as trigger:
        handler2.do_POST()
        trigger.assert_called_once()
        assert handler2._code == 202

    feature_body = json.dumps({"ref": "refs/heads/feature/x"}).encode("utf-8")
    handler3 = RecordingHandler(
        FakeConnection(WEBHOOK_PATH, feature_body, "push"), ("127.0.0.1", 12345), httpd
    )
    with patch("github_webhook_server.trigger_sync_background") as trigger:
        handler3.do_POST()
        trigger.assert_not_called()
        assert handler3._code == 200
