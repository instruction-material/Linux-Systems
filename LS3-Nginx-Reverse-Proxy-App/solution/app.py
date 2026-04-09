from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import json
import os
import time


class Handler(BaseHTTPRequestHandler):
	server_version = "LinuxToyApp/1.0"

	def _write_json(self, payload, status=200):
		encoded = json.dumps(payload).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(encoded)))
		self.end_headers()
		self.wfile.write(encoded)

	def do_GET(self):
		parsed = urlparse(self.path)
		query = parse_qs(parsed.query)
		self._write_json({
			"service": "linux-toy-app",
			"path": parsed.path,
			"query": query,
			"message": "Reverse proxy lab solution",
			"timestamp": int(time.time())
		})


def main():
	port = int(os.environ.get("APP_PORT", "8081"))
	server = HTTPServer(("127.0.0.1", port), Handler)
	print(f"Listening on http://127.0.0.1:{port}", flush=True)
	server.serve_forever()


if __name__ == "__main__":
	main()
