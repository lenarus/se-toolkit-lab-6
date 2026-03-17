import os
import sys
import json
import time
import socket
import subprocess
import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer


def _run_test_server(port, first_tool_name, first_tool_args, final_content):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                self.rfile.read(length)
            self.server.request_count = getattr(self.server, "request_count", 0) + 1

            if self.server.request_count == 1:
                # Instruct the agent to call a tool (function_call)
                resp = {
                    "created": 0,
                    "model": "test-model",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "function_call": {
                                    "name": first_tool_name,
                                    "arguments": json.dumps(first_tool_args),
                                },
                            },
                            "finish_reason": "function_call",
                        }
                    ],
                }
            else:
                # Final assistant response after the tool result is provided
                resp = {
                    "created": 0,
                    "model": "test-model",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": final_content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                }

            body = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    addr = s.getsockname()
    s.close()
    return addr[1]


def _run_agent_and_capture(port, question):
    env = os.environ.copy()
    env["LLM_API_BASE"] = f"http://127.0.0.1:{port}/v1"
    env["LLM_API"] = "test-key"
    env["LLM_API_MODEL"] = "test-model"
    env["LLM_MODEL"] = "test-model"

    repo_root = os.path.dirname(os.path.dirname(__file__))
    cmd = [sys.executable, os.path.join(repo_root, "agent.py"), question]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, env=env, cwd=repo_root, timeout=15
    )
    return completed


def test_framework_question_triggers_read_file():
    port = _get_free_port()
    server_proc = multiprocessing.Process(
        target=_run_test_server,
        args=(
            port,
            "read_file",
            {"path": "backend/app/main.py"},
            "The backend uses FastAPI. Source: backend/app/main.py",
        ),
        daemon=True,
    )
    server_proc.start()

    try:
        time.sleep(0.1)
        completed = _run_agent_and_capture(port, "What framework does the backend use?")

        assert completed.returncode == 0, (
            f"agent exited non-zero; stderr: {completed.stderr}"
        )
        out = completed.stdout.strip()
        assert out, f"No stdout captured; stderr: {completed.stderr}"
        obj = json.loads(out)

        assert "answer" in obj and isinstance(obj["answer"], str)
        assert "tool_calls" in obj and isinstance(obj["tool_calls"], list)
        assert any(c.get("tool") == "read_file" for c in obj["tool_calls"]), (
            "read_file not called"
        )
    finally:
        if server_proc.is_alive():
            server_proc.terminate()
            server_proc.join(timeout=1)


def test_items_question_triggers_query_api():
    port = _get_free_port()
    server_proc = multiprocessing.Process(
        target=_run_test_server,
        args=(
            port,
            "query_api",
            {"method": "GET", "path": "/items/"},
            "There are 42 items in the database. Source: api:/items/",
        ),
        daemon=True,
    )
    server_proc.start()

    try:
        time.sleep(0.1)
        completed = _run_agent_and_capture(port, "How many items are in the database?")

        assert completed.returncode == 0, (
            f"agent exited non-zero; stderr: {completed.stderr}"
        )
        out = completed.stdout.strip()
        assert out, f"No stdout captured; stderr: {completed.stderr}"
        obj = json.loads(out)

        assert "answer" in obj and isinstance(obj["answer"], str)
        assert "tool_calls" in obj and isinstance(obj["tool_calls"], list)
        assert any(c.get("tool") == "query_api" for c in obj["tool_calls"]), (
            "query_api not called"
        )
        # optional: check source uses api:
        assert obj.get("source", "").startswith("api:"), (
            "source should indicate api path"
        )
    finally:
        if server_proc.is_alive():
            server_proc.terminate()
            server_proc.join(timeout=1)
