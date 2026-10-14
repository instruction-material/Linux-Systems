"""Owned loopback HTTP application for the Linux reverse-proxy lab."""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

SERVICE = "linux-toy-app"
MAX_TARGET_LENGTH = 4096
MAX_QUERY_FIELDS = 16


def inspection_payload(path, query, peer, headers):
    return {"service": SERVICE, "path": path, "query": query,
            "peer": peer, "headers": headers}


class Handler(BaseHTTPRequestHandler):
    server_version = "LinuxToyApp/1.0"

    def reply(self, status, payload):
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if status == 405:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def do_GET(self):
        if len(self.path) > MAX_TARGET_LENGTH:
            self.reply(414, {"error": "request_target_too_long"})
            return
        try:
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True,
                             max_num_fields=MAX_QUERY_FIELDS)
        except ValueError:
            self.reply(400, {"error": "invalid_query"})
            return
        if parsed.path == "/health":
            self.reply(200, {"service": SERVICE, "status": "ok"})
        elif parsed.path == "/inspect":
            headers = {name: self.headers.get(name, "") for name in
                       ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto")}
            payload = inspection_payload(parsed.path, query, self.client_address[0], headers)
            if payload is None:
                self.reply(501, {"error": "inspection_not_implemented"})
            else:
                self.reply(200, payload)
        else:
            self.reply(404, {"error": "not_found"})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        self.reply(405, {"error": "method_not_allowed"})


def main():
    value = os.environ.get("APP_PORT", "8081")
    if not re.fullmatch(r"[1-9][0-9]{3,4}", value) or not 1024 <= int(value) <= 65535:
        print("APP_PORT must be an ASCII integer from 1024 through 65535.", file=sys.stderr)
        return 2
    port = int(value)
    try:
        with HTTPServer(("127.0.0.1", port), Handler) as server:
            print(f"Listening on http://127.0.0.1:{port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                return 0
    except OSError as error:
        print(f"Cannot start the owned loopback app: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
