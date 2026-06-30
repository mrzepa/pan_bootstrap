#!/usr/bin/env python3
"""Serve the local bootstrap GUI and save vars/firewalls.yml."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "webgui"
OUTPUT_FILE = PROJECT_ROOT / "vars" / "firewalls.yml"


class BootstrapGuiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/api/save-yaml":
            self.send_error(404, "Not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        yaml_text = payload.get("yaml")
        if not isinstance(yaml_text, str) or not yaml_text.strip():
            self.send_error(400, "Missing yaml")
            return

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(yaml_text, encoding="utf-8")

        response = {
            "ok": True,
            "path": str(OUTPUT_FILE),
            "bytes": len(yaml_text.encode("utf-8")),
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8081), BootstrapGuiHandler)
    print("Serving Palo Alto bootstrap GUI at http://127.0.0.1:8081/")
    print(f"Saving generated YAML to {OUTPUT_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
