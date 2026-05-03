"""Toy hardened HTTP target for demonstrating expected secure behavior.

This target receives the same scenario input as the toy vulnerable agent
in this directory, but applies a strict trust boundary: anything in
``input.context`` whose ``trust`` is not ``trusted`` is treated as data,
never as instruction. The user's original request stays the goal.

Running the harness against this target should *pass* the
``no_denied_tool_call`` assertion on the bundled
``scenarios/goal_hijack/outbound_email_exfiltration_001.yaml`` scenario,
demonstrating what a correctly-behaving agent looks like to the harness.

This agent is intentionally minimal. It is not a production guidance
template; its job is to give the harness a positive control to compare
the vulnerable demo agent against.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from agent_harness.recorder import TraceRecorder


HOST = "127.0.0.1"
PORT = 8002

UNTRUSTED_TRUST_LEVELS = frozenset({"untrusted", "unknown"})


def collect_trusted_text(context: list[dict[str, Any]]) -> str:
    """Concatenate text from context entries explicitly marked trusted."""
    parts: list[str] = []

    for entry in context:
        if not isinstance(entry, dict):
            continue

        if entry.get("trust") != "trusted":
            continue

        content = entry.get("content")

        if isinstance(content, str):
            parts.append(content)

    return "\n".join(parts)


def has_untrusted_context(context: list[dict[str, Any]]) -> bool:
    """Report whether any context entry is marked untrusted or unknown."""
    for entry in context:
        if isinstance(entry, dict) and entry.get("trust") in UNTRUSTED_TRUST_LEVELS:
            return True

    return False


def build_trace(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a trace dict that demonstrates trust-boundary preservation."""
    scenario_input = payload.get("input", {}) or {}
    user_message = scenario_input.get("user_message", "") or ""
    context = scenario_input.get("context", []) or []

    trusted_text = collect_trusted_text(context)

    if trusted_text:
        assistant_text = (
            "Based on the available trusted content, here is a brief summary."
        )
    else:
        assistant_text = (
            "I cannot find any trusted source content to summarize, so I "
            "cannot complete the request."
        )

    recorder = TraceRecorder()
    recorder.add_message("user", user_message)
    recorder.add_message("assistant", assistant_text)

    if has_untrusted_context(context):
        recorder.add_event(
            event_type="untrusted_context_received",
            policy="treated as data, not instruction",
        )

    return recorder.to_dict()


class HardenedAgentRequestHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the toy hardened agent target."""

    def do_POST(self) -> None:
        """Handle POST /run requests."""
        if self.path != "/run":
            self.send_error(404, "not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length)
        payload = json.loads(request_body.decode("utf-8"))

        trace = build_trace(payload)

        response_body = json.dumps(trace).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format: str, *args: Any) -> None:
        """Silence default request logging for cleaner demo output."""
        return


def main() -> None:
    """Run the toy hardened HTTP agent target."""
    server = HTTPServer((HOST, PORT), HardenedAgentRequestHandler)
    print(f"hardened_http_agent listening on http://{HOST}:{PORT}/run")
    server.serve_forever()


if __name__ == "__main__":
    main()
