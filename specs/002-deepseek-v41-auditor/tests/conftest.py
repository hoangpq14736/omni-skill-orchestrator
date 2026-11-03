"""
Test fixtures and mock DeepSeek HTTP server harness for Omni-Auditor v4.1 tests.
Zero external dependencies: 100% Python Standard Library (http.server, threading, json, ssl).
"""

import http.server
import json
import socketserver
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class MockDeepSeekHandler(http.server.BaseHTTPRequestHandler):
    """
    Configurable HTTP request handler simulating DeepSeek v4.1 API behaviors.
    """
    server_controller: Any = None

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP access logs during testing
        pass

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        request_record = {
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
            "timestamp": time.monotonic()
        }
        
        if self.server_controller:
            self.server_controller.record_request(request_record)
            handler_fn = self.server_controller.get_handler_for_request(self.server_controller.request_count)
            if handler_fn:
                handler_fn(self, request_record)
                return

        # Default fallback: return valid 200 OK critique
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        
        default_resp = {
            "id": "mock-deepseek-audit-001",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({
                            "verdict": "REJECTED",
                            "confidence_score": 0.95,
                            "summary": "Mock audit: 3 critical flaws identified.",
                            "critical_vulnerabilities": [
                                {
                                    "id": "VULN-001",
                                    "severity": "CRITICAL",
                                    "title": "Raw SQL concatenation",
                                    "description": "Found unparameterized SQL cursor execution.",
                                    "remediation": "Use ? placeholders."
                                },
                                {
                                    "id": "VULN-002",
                                    "severity": "HIGH",
                                    "title": "Synchronous network call in reflex hook",
                                    "description": "Blocks execution and violates Principle I.",
                                    "remediation": "Move to out-of-band worker."
                                },
                                {
                                    "id": "VULN-003",
                                    "severity": "HIGH",
                                    "title": "Unredacted API keys",
                                    "description": "Secrets leaked in logs.",
                                    "remediation": "Pass through sanitizer."
                                }
                            ],
                            "concurrency_hazards": [],
                            "edge_cases": [],
                            "prescriptive_directives": ["Fix raw SQL", "Remove sync network call", "Redact secrets"]
                        })
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 250,
                "total_tokens": 370
            }
        }
        self.wfile.write(json.dumps(default_resp).encode("utf-8"))


class MockDeepSeekServer:
    """
    Ephemeral Mock DeepSeek Server lifecycle manager.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.server: Optional[http.server.HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.requests: List[Dict[str, Any]] = []
        self.request_count: int = 0
        self.custom_handlers: Dict[int, Callable] = {}
        self.fallback_handler: Optional[Callable] = None

    def record_request(self, req: Dict[str, Any]) -> None:
        self.requests.append(req)
        self.request_count += 1

    def set_handler(self, request_index: int, handler_fn: Callable) -> None:
        self.custom_handlers[request_index] = handler_fn

    def set_fallback_handler(self, handler_fn: Callable) -> None:
        self.fallback_handler = handler_fn

    def get_handler_for_request(self, count: int) -> Optional[Callable]:
        if count in self.custom_handlers:
            return self.custom_handlers[count]
        return self.fallback_handler

    def start(self) -> str:
        handler_cls = type(
            "BoundMockHandler",
            (MockDeepSeekHandler,),
            {"server_controller": self}
        )
        self.server = http.server.HTTPServer((self.host, self.port), handler_cls)
        actual_port = self.server.server_address[1]
        self.port = actual_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            self.thread = None


def make_approved_response(edge_cases_count: int = 3) -> Dict[str, Any]:
    """Helper to produce a schema-compliant APPROVED response with >= 3 edge cases."""
    edge_cases = []
    for i in range(1, edge_cases_count + 1):
        edge_cases.append({
            "scenario": f"Edge case {i}: Network socket timeout during heavy load",
            "consequence": "Request dropped",
            "mitigation": "Clamped jitter backoff with fail-fast budget abort"
        })
    return {
        "id": "mock-approved-001",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "verdict": "APPROVED",
                        "confidence_score": 0.99,
                        "summary": "Architecture is verified 100% sound and constitutional.",
                        "critical_vulnerabilities": [],
                        "concurrency_hazards": [],
                        "edge_cases": edge_cases,
                        "prescriptive_directives": ["Proceed to implementation."]
                    })
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 150, "total_tokens": 250}
    }
