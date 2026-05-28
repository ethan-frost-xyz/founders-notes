#!/usr/bin/env python3
"""Minimal GitHub push webhook → background sync-and-index.sh (Mac mini).

Listens on localhost; expose via Tailscale Funnel. Requires GITHUB_WEBHOOK_SECRET.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876
WEBHOOK_PATH = "/github"
LOG_NAME = "founders.github_webhook"


def _vault_root() -> Path:
    raw = os.environ.get("VAULT_ROOT", "").strip()
    if not raw:
        raise RuntimeError("VAULT_ROOT is not set")
    return Path(raw).expanduser().resolve()


def _webhook_secret() -> str:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise RuntimeError("GITHUB_WEBHOOK_SECRET is not set")
    return secret


def verify_github_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[7:], expected)


def should_trigger_sync(event: str, payload: dict[str, Any]) -> bool:
    if event == "ping":
        return False
    if event != "push":
        return False
    ref = payload.get("ref")
    return ref == "refs/heads/main"


def trigger_sync_background(vault_root: Path, *, log_path: Path | None = None) -> None:
    script = vault_root / "services" / "telegram" / "deploy" / "sync-and-index.sh"
    if not script.is_file():
        raise FileNotFoundError(f"sync script not found: {script}")
    log_path = log_path or (
        Path.home() / "Library" / "Logs" / "founders-telegram" / "sync.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fd = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    subprocess.Popen(
        [str(script)],
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        cwd=str(vault_root),
        start_new_session=True,
    )


class GitHubWebhookHandler(BaseHTTPRequestHandler):
    server_version = "FoundersGitHubWebhook/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        logging.getLogger(LOG_NAME).info("%s - %s", self.address_string(), fmt % args)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != WEBHOOK_PATH:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        secret = self.server.webhook_secret  # type: ignore[attr-defined]
        sig = self.headers.get("X-Hub-Signature-256")
        if not verify_github_signature(secret, body, sig):
            self.send_error(401, "invalid signature")
            return
        event = self.headers.get("X-GitHub-Event", "")
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return
        if not isinstance(payload, dict):
            payload = {}
        if event == "ping":
            self._respond(200, "pong")
            return
        if should_trigger_sync(event, payload):
            vault_root = self.server.vault_root  # type: ignore[attr-defined]
            log_path = self.server.sync_log_path  # type: ignore[attr-defined]
            trigger_sync_background(vault_root, log_path=log_path)
            self._respond(202, "sync scheduled")
            return
        self._respond(200, "ignored")

    def _respond(self, code: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    vault_root: Path | None = None,
    webhook_secret: str | None = None,
    sync_log_path: Path | None = None,
) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    vault_root = vault_root or _vault_root()
    webhook_secret = webhook_secret or _webhook_secret()
    sync_log_path = sync_log_path or (
        Path.home() / "Library" / "Logs" / "founders-telegram" / "sync.log"
    )
    httpd = HTTPServer((host, port), GitHubWebhookHandler)
    httpd.vault_root = vault_root  # type: ignore[attr-defined]
    httpd.webhook_secret = webhook_secret  # type: ignore[attr-defined]
    httpd.sync_log_path = sync_log_path  # type: ignore[attr-defined]
    logging.getLogger(LOG_NAME).info(
        "listening on http://%s:%s%s (vault=%s)",
        host,
        port,
        WEBHOOK_PATH,
        vault_root,
    )
    httpd.serve_forever()


def main() -> int:
    host = os.environ.get("GITHUB_WEBHOOK_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    port_raw = os.environ.get("GITHUB_WEBHOOK_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(port_raw)
    except ValueError:
        print(f"invalid GITHUB_WEBHOOK_PORT: {port_raw!r}", file=sys.stderr)
        return 1
    try:
        serve(host=host, port=port)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logging.getLogger(LOG_NAME).exception("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
