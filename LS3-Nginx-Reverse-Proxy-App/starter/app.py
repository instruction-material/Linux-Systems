from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {
            "service": "linux-toy-app",
            "path": self.path,
            "message": "Reverse proxy lab starter",
        }
        encoded = json.dumps(body).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    port = int(os.environ.get("APP_PORT", "8081"))
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Listening on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
