import os
import sys
import json
import time
import socket
import subprocess
import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer


# Helper to run a simple stateful test LLM server that first returns a function_call
# and on the next request returns a final assistant content.
def _run_test_server(port, first_tool_name, first_tool_path, final_content):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                self.rfile.read(length)
            # maintain simple request counter on the server instance
            self.server.request_count = getattr(self.server, "request_count", 0) + 1

            if self.server.request_count == 1:
                # instruct the model to call a tool
                resp = {
                    "created": 0,
                    "model": "test-model",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "function_call": {
                                    "name": first_tool_name,
                                    "arguments": json.dumps({"path": first_tool_path}),
                                },
                            },
                            "finish_reason": "function_call",
                        }
                    ],
                }
            else:
                # final assistant response after tool result is provided
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


def _run_agent_and_parse(port, question):
    # prepare env to point agent at the test server
    env = os.environ.copy()
    env["LLM_API_BASE"] = f"http://127.0.0.1:{port}/v1"
    env["LLM_API_KEY"] = "test-key"
    env["LLM_MODEL"] = "test-model"

    repo_root = os.path.dirname(os.path.dirname(__file__))
    cmd = [sys.executable, os.path.join(repo_root, "agent.py"), question]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, env=env, cwd=repo_root, timeout=15
    )
    return completed


def test_resolve_merge_conflict_triggers_read_file_and_sets_source():
    port = _get_free_port()
    # server will ask the agent to call read_file on wiki/git-workflow.md,
    # then return a final assistant answer mentioning the source.
    server_proc = multiprocessing.Process(
        target=_run_test_server,
        args=(
            port,
            "read_file",
            "wiki/git-workflow.md",
            "To resolve a merge conflict, edit the conflicting file, choose changes, stage and commit. Source: wiki/git-workflow.md",
        ),
        daemon=True,
    )
    server_proc.start()

    try:
        time.sleep(0.1)  # allow server to start
        completed = _run_agent_and_parse(port, "How do you resolve a merge conflict?")

        assert completed.returncode == 0, (
            f"agent exited non-zero; stderr: {completed.stderr}"
        )
        out = completed.stdout.strip()
        assert out, f"No stdout captured; stderr: {completed.stderr}"
        obj = json.loads(out)

        assert "answer" in obj and isinstance(obj["answer"], str)
        assert "tool_calls" in obj and isinstance(obj["tool_calls"], list)

        # Expect a read_file call
        assert any(c.get("tool") == "read_file" for c in obj["tool_calls"]), (
            "read_file not called"
        )
        # Expect source to be the wiki path requested by the model
        assert obj.get("source") == "wiki/git-workflow.md"
    finally:
        if server_proc.is_alive():
            server_proc.terminate()
            server_proc.join(timeout=1)


def test_list_wiki_files_triggers_list_files_call():
    port = _get_free_port()
    server_proc = multiprocessing.Process(
        target=_run_test_server,
        args=(
            port,
            "list_files",
            "wiki",
            "The wiki contains README.md and guides. Source: wiki",
        ),
        daemon=True,
    )
    server_proc.start()

    try:
        time.sleep(0.1)
        completed = _run_agent_and_parse(port, "What files are in the wiki?")

        assert completed.returncode == 0, (
            f"agent exited non-zero; stderr: {completed.stderr}"
        )
        out = completed.stdout.strip()
        assert out, f"No stdout captured; stderr: {completed.stderr}"
        obj = json.loads(out)

        assert "answer" in obj and isinstance(obj["answer"], str)
        assert "tool_calls" in obj and isinstance(obj["tool_calls"], list)

        # Expect a list_files call
        assert any(c.get("tool") == "list_files" for c in obj["tool_calls"]), (
            "list_files not called"
        )
    finally:
        if server_proc.is_alive():
            server_proc.terminate()
            server_proc.join(timeout=1)
