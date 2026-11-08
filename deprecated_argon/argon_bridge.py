#!/usr/bin/env python3
"""
Argon Bridge Server (Localhost)
Connects Google Antigravity with Gemini 4 Argon on Gemini Chat (Web UI).

Standard Library only - Zero external dependencies.
Port: 7890
"""

import http.server
import json
import logging
import sys
import threading
import time
import uuid
from typing import Dict, Optional

PORT = 7890
HOST = "127.0.0.1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ArgonBridge] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ArgonBridge")

# Global State
class BridgeState:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending_tasks: Dict[str, str] = {}         # task_id -> prompt
        self.in_flight_tasks: Dict[str, float] = {}      # task_id -> timestamp
        self.completed_tasks: Dict[str, str] = {}        # task_id -> reply
        self.task_events: Dict[str, threading.Event] = {} # task_id -> Event
        self.last_agent_seen: float = 0.0                # timestamp when Tampermonkey polled
        self.is_agent_online: bool = False

state = BridgeState()


class ArgonBridgeHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            now = time.time()
            online = (now - state.last_agent_seen) < 5.0
            self._send_json(200, {
                "status": "ok",
                "argon_connected": online,
                "seconds_since_last_poll": round(now - state.last_agent_seen, 1) if state.last_agent_seen else -1,
                "pending_tasks": len(state.pending_tasks)
            })

        elif self.path == "/poll":
            state.last_agent_seen = time.time()
            state.is_agent_online = True

            with state.lock:
                if state.pending_tasks:
                    task_id, prompt = next(iter(state.pending_tasks.items()))
                    del state.pending_tasks[task_id]
                    state.in_flight_tasks[task_id] = time.time()
                    logger.info(f"Dispatched task {task_id} to Tampermonkey (Prompt len: {len(prompt)})")
                    self._send_json(200, {
                        "has_task": True,
                        "task_id": task_id,
                        "prompt": prompt
                    })
                    return

            self._send_json(200, {"has_task": False})

        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON: {str(e)}"})
            return

        # Antigravity asking a question to Argon
        if self.path == "/ask":
            prompt = payload.get("prompt", "").strip()
            timeout = float(payload.get("timeout", 180.0)) # default 3 minutes for deep reasoning

            if not prompt:
                self._send_json(400, {"error": "Missing 'prompt' in request body"})
                return

            task_id = str(uuid.uuid4())[:8]
            event = threading.Event()

            with state.lock:
                state.pending_tasks[task_id] = prompt
                state.task_events[task_id] = event

            logger.info(f"Queued task {task_id}. Waiting up to {timeout}s for Argon response...")

            # Wait for Tampermonkey to fulfill
            completed = event.wait(timeout=timeout)

            with state.lock:
                if completed and task_id in state.completed_tasks:
                    reply = state.completed_tasks.pop(task_id)
                    state.in_flight_tasks.pop(task_id, None)
                    state.task_events.pop(task_id, None)
                    logger.info(f"Task {task_id} fulfilled successfully. Reply len: {len(reply)}")
                    self._send_json(200, {"status": "ok", "task_id": task_id, "reply": reply})
                else:
                    state.pending_tasks.pop(task_id, None)
                    state.in_flight_tasks.pop(task_id, None)
                    state.task_events.pop(task_id, None)
                    logger.warning(f"Task {task_id} timed out after {timeout}s.")
                    self._send_json(504, {
                        "status": "timeout",
                        "task_id": task_id,
                        "error": f"Argon did not respond within {timeout}s. Check if Gemini web tab is active."
                    })

        # Tampermonkey returning the answer from Argon
        elif self.path == "/reply":
            task_id = payload.get("task_id")
            reply = payload.get("reply", "")

            if not task_id:
                self._send_json(400, {"error": "Missing 'task_id'"})
                return

            with state.lock:
                state.completed_tasks[task_id] = reply
                if task_id in state.task_events:
                    state.task_events[task_id].set()

            logger.info(f"Received answer from Argon for task {task_id} (Length: {len(reply)} chars)")
            self._send_json(200, {"status": "received", "task_id": task_id})

        else:
            self._send_json(404, {"error": "Not found"})

    def log_message(self, format, *args):
        # Suppress noisy standard poll logs
        if "GET /poll" in args[0] or "GET /health" in args[0]:
            return
        super().log_message(format, *args)


def run_server():
    server = http.server.ThreadingHTTPServer((HOST, PORT), ArgonBridgeHandler)
    logger.info(f"🚀 Argon Bridge Server is listening on http://{HOST}:{PORT}")
    logger.info("Keep this terminal open, and keep gemini.google.com open in your browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Argon Bridge.")
        server.server_close()


if __name__ == "__main__":
    run_server()
