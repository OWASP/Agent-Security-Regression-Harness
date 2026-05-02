"""Example HTTP target for live harness testing."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


HOST = "127.0.0.1"
PORT = 8000


class AgentRequestHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the example agent target."""

    def do_POST(self) -> None:
        """Handle POST /run requests."""
        if self.path != "/run":
            self.send_error(404, "not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length)
        payload = json.loads(request_body.decode("utf-8"))
        scenario_input = payload.get("input", {})
        user_message = scenario_input.get("user_message", "")

        trace: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": user_message,
                },
                {
                    "role": "assistant",
                    "content": "Here is the summary.",
                },
            ],
            "tool_calls": [],
            "events": [],
        }

        response_body = json.dumps(trace).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

def main() -> None:
    """Run the example HTTP target server."""
    server = HTTPServer((HOST, PORT), AgentRequestHandler)
    print(f"Example HTTP target listening on http://{HOST}:{PORT}/run")
    server.serve_forever()

if __name__ == "__main__":
    main()


