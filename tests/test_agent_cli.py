import os
import sys
import json
import time
import socket
import subprocess
import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer


def _run_test_server(port):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            # read and ignore request body
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                self.rfile.read(length)
            resp = {
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "4"},
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
            # silence server logs during tests
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


def test_agent_cli_returns_json_answer_and_tool_calls():
    # start local fake LLM server
    port = _get_free_port()
    server_proc = multiprocessing.Process(
        target=_run_test_server, args=(port,), daemon=True
    )
    server_proc.start()

    try:
        # wait briefly for server to come up
        time.sleep(0.1)

        # Prepare environment for subprocess (override LLM config so no external calls)
        env = os.environ.copy()
        env["LLM_API_BASE"] = f"http://127.0.0.1:{port}/v1"
        env["LLM_API_KEY"] = "test-key"
        env["LLM_MODEL"] = "test-model"

        # Run agent.py as a subprocess
        repo_root = os.path.dirname(os.path.dirname(__file__))
        cmd = [sys.executable, os.path.join(repo_root, "agent.py"), "What is 2+2?"]
        completed = subprocess.run(
            cmd, capture_output=True, text=True, env=env, cwd=repo_root, timeout=10
        )

        # Ensure process exited successfully
        assert completed.returncode == 0, (
            f"agent exited non-zero; stderr: {completed.stderr}"
        )

        # Only valid JSON must be on stdout
        out = completed.stdout.strip()
        assert out, f"No stdout captured; stderr: {completed.stderr}"
        obj = json.loads(out)

        # Validate required schema
        assert "answer" in obj, "Missing 'answer' in output JSON"
        assert "tool_calls" in obj, "Missing 'tool_calls' in output JSON"
        assert isinstance(obj["answer"], str), "'answer' must be a string"
        assert isinstance(obj["tool_calls"], list), "'tool_calls' must be a list"

        # Validate content produced by the fake server
        assert obj["answer"].strip() == "4"
        assert obj["tool_calls"] == []

    finally:
        if server_proc.is_alive():
            server_proc.terminate()
            server_proc.join(timeout=1)


# ```// filepath: /home/lenarus/Projects/se-toolkit-lab-6/tests/test_agent_cli.py
import os
import sys
import json
import time
import socket
import subprocess
import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer


def _run_test_server(port):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            # read and ignore request body
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                self.rfile.read(length)
            resp = {
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "4"},
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
            # silence server logs during tests
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


def test_agent_cli_returns_json_answer_and_tool_calls():
    # start local fake LLM server
    port = _get_free_port()
    server_proc = multiprocessing.Process(
        target=_run_test_server, args=(port,), daemon=True
    )
    server_proc.start()

    try:
        # wait briefly for server to come up
        time.sleep(0.1)

        # Prepare environment for subprocess (override LLM config so no external calls)
        env = os.environ.copy()
        env["LLM_API_BASE"] = f"http://127.0.0.1:{port}/v1"
        env["LLM_API_KEY"] = "-key"
        env["LLM_MODEL"] = "test-model"

        # Run agent.py as a subprocess
        repo_root = os.path.dirname(os.path.dirname(__file__))
        cmd = [sys.executable, os.path.join(repo_root, "agent.py"), "What is 2+2?"]
        completed = subprocess.run(
            cmd, capture_output=True, text=True, env=env, cwd=repo_root, timeout=10
        )

        # Ensure process exited successfully
        assert completed.returncode == 0, (
            f"agent exited non-zero; stderr: {completed.stderr}"
        )

        # Only valid JSON must be on stdout
        out = completed.stdout.strip()
        assert out, f"No stdout captured; stderr: {completed.stderr}"
        obj = json.loads(out)

        # Validate required schema
        assert "answer" in obj, "Missing 'answer' in output JSON"
        assert "tool_calls" in obj, "Missing 'tool_calls' in output JSON"
        assert isinstance(obj["answer"], str), "'answer' must be a string"
        assert isinstance(obj["tool_calls"], list), "'tool_calls' must be a list"

        # Validate content produced by the fake server
        assert obj["answer"].strip() == "4"
        assert obj["tool_calls"] == []

    finally:
        if server_proc.is_alive():
            server_proc.terminate()
            server_proc.join(timeout=1)
