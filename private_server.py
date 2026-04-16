#!/usr/bin/env python3
import base64
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


USERNAME = os.environ.get("BASIC_AUTH_USER", "memo2")
PASSWORD = os.environ.get("BASIC_AUTH_PASS", "growth2026")
REALM = "Private Preview"


def expected_header() -> str:
    token = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


class AuthHandler(SimpleHTTPRequestHandler):
    def _unauthorized(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        self.end_headers()
        self.wfile.write(b"Authentication required.")

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == expected_header()

    def do_GET(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        super().do_HEAD()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AuthHandler)
    print(f"Serving private preview on port {port}")
    server.serve_forever()
