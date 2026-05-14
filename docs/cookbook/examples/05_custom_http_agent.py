"""Runnable minimal HTTP agent for the harness.

Usage:
    Terminal 1:  python docs/cookbook/examples/05_custom_http_agent.py
    Terminal 2:  agent-harness run docs/cookbook/examples/01_hello_scenario.yaml \\
                    --live --target-url http://127.0.0.1:9000/run
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json


VERSION = "0.0.1"
HOST = "127.0.0.1"
PORT = 9000


class DemoAgent(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        msg = body.get("input", {}).get("user_message", "")
        trace = json.dumps(
            {
                "messages": [
                    {"role": "user", "content": msg},
                    {"role": "assistant", "content": f"Reply: {msg}"},
                ],
                "tool_calls": [],
                "events": [{"type": "goal", "id": "summarize_document"}],
            }
        )
        body_bytes = trace.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), DemoAgent)
    print(f"Cookbook demo agent on http://{HOST}:{PORT}/run")
    server.serve_forever()
