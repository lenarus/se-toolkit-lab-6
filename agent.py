#!/usr/bin/env python3
import os
import sys
import json
import pathlib

try:
    import requests
except Exception:
    print(
        "Missing dependency: requests. Install with: pip install requests",
        file=sys.stderr,
    )
    sys.exit(1)


def load_env_file(path):
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # Do not overwrite existing environment vars
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"Failed to load env file {path}: {e}", file=sys.stderr)


def safe_resolve_project_path(
    project_root: pathlib.Path, rel_path: str
) -> pathlib.Path:
    # Reject obvious bad inputs
    if not rel_path or rel_path.startswith(("..", "/", "\\")):
        raise ValueError("invalid path")
    # Normalize
    candidate = (project_root / rel_path).resolve()
    # Ensure candidate is inside project root
    try:
        if not candidate.is_relative_to(project_root.resolve()):
            raise ValueError("path outside project")
    except AttributeError:
        # Fallback for older Python: string prefix check
        proj = str(project_root.resolve())
        cand = str(candidate)
        if not cand.startswith(proj):
            raise ValueError("path outside project")
    return candidate


def read_file_impl(project_root: pathlib.Path, rel_path: str) -> str:
    try:
        p = safe_resolve_project_path(project_root, rel_path)
    except Exception as e:
        return f"ERROR: invalid path: {rel_path} ({e})"

    if not p.exists():
        return f"ERROR: not found: {rel_path}"
    if p.is_dir():
        return f"ERROR: path is a directory: {rel_path}"

    max_bytes = 200 * 1024  # 200 KiB
    try:
        with open(p, "rb") as f:
            data = f.read(max_bytes + 1)
            if len(data) > max_bytes:
                try:
                    text = data[:max_bytes].decode("utf-8", errors="replace")
                except Exception:
                    text = data[:max_bytes].decode("latin-1", errors="replace")
                return f"(TRUNCATED) {text}"
            try:
                return data.decode("utf-8")
            except Exception:
                return data.decode("latin-1", errors="replace")
    except Exception as e:
        return f"ERROR: reading file {rel_path}: {e}"


def list_files_impl(project_root: pathlib.Path, rel_path: str) -> str:
    try:
        p = safe_resolve_project_path(project_root, rel_path)
    except Exception as e:
        return f"ERROR: invalid path: {rel_path} ({e})"

    if not p.exists():
        return f"ERROR: not found: {rel_path}"
    if not p.is_dir():
        return f"ERROR: not a directory: {rel_path}"

    try:
        entries = sorted(os.listdir(p))
        max_entries = 500
        truncated = False
        if len(entries) > max_entries:
            entries = entries[:max_entries]
            truncated = True
        out = "\n".join(entries)
        if truncated:
            out = out + f"\n(TRUNCATED, {len(entries)} of many entries shown)"
        return out
    except Exception as e:
        return f"ERROR: listing directory {rel_path}: {e}"


def main():
    # Load .env.agent.secret if present in project root
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = pathlib.Path(here)
    env_path = os.path.join(here, ".env.agent.secret")
    load_env_file(env_path)

    if len(sys.argv) < 2:
        print('Usage: agent.py "Your question here"', file=sys.stderr)
        sys.exit(2)

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Empty question provided.", file=sys.stderr)
        sys.exit(2)

    LLM_API_KEY = os.environ.get("LLM_API_KEY")
    LLM_API_BASE = os.environ.get("LLM_API_BASE")
    LLM_MODEL = os.environ.get("LLM_MODEL")

    if not LLM_API_KEY or not LLM_API_BASE or not LLM_MODEL:
        print(
            "Missing LLM configuration. Ensure LLM_API_KEY, LLM_API_BASE, LLM_MODEL are set (e.g. in .env.agent.secret).",
            file=sys.stderr,
        )
        sys.exit(1)

    endpoint = LLM_API_BASE.rstrip("/") + "/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    # Define function (tool) schemas for function-calling
    functions = [
        {
            "name": "list_files",
            "description": "List files and directories at a given relative path under the project root. Return newline-separated entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (no .. allowed)",
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "read_file",
            "description": "Read a text file from the project repository and return its contents. Path must be relative and inside project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path from project root (no .. allowed)",
                    }
                },
                "required": ["path"],
            },
        },
    ]

    system_prompt = (
        "You are a helpful assistant that can inspect the repository using two tools: "
        "list_files(path) and read_file(path). Use list_files to discover files and "
        "read_file to read file contents. When you want the program to run a tool, "
        "emit a function call using the declared schema. When finished, return a concise answer "
        "and include the source file path as 'Source: <path>' or provide the most relevant file path."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    tool_calls = []
    final_answer = None
    max_tool_calls = 10
    call_count = 0

    while True:
        if call_count > max_tool_calls:
            print("Exceeded maximum tool calls", file=sys.stderr)
            break

        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "functions": functions,
            "function_call": "auto",
        }

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=55)
        except requests.exceptions.RequestException as e:
            print(f"LLM request failed: {e}", file=sys.stderr)
            sys.exit(1)

        if resp.status_code != 200:
            print(
                f"LLM returned status {resp.status_code}: {resp.text}", file=sys.stderr
            )
            sys.exit(1)

        try:
            data = resp.json()
        except Exception as e:
            print(f"Failed to parse JSON from LLM response: {e}", file=sys.stderr)
            sys.exit(1)

        choices = data.get("choices", [])
        if not choices:
            print("LLM response contains no choices", file=sys.stderr)
            sys.exit(1)
        first = choices[0]
        msg = first.get("message") if isinstance(first, dict) else None
        if not msg:
            print("LLM response missing message field", file=sys.stderr)
            sys.exit(1)

        # If the model requested a function call
        function_call = msg.get("function_call")
        if function_call:
            name = function_call.get("name")
            args_text = function_call.get("arguments", "{}")
            try:
                args = (
                    json.loads(args_text) if isinstance(args_text, str) else args_text
                )
            except Exception:
                # sometimes the model returns non-strict JSON; fail gracefully
                args = {}
            call_count += 1

            # Execute the tool
            if name == "read_file":
                path_arg = args.get("path", "")
                result = read_file_impl(project_root, path_arg)
            elif name == "list_files":
                path_arg = args.get("path", "")
                result = list_files_impl(project_root, path_arg)
            else:
                result = f"ERROR: unknown tool {name}"

            # Record the tool call
            tool_calls.append({"tool": name, "args": args, "result": result})

            # Append tool result as a tool-role message for the model to consume
            messages.append({"role": "tool", "name": name, "content": result})
            # Continue the loop so the model can respond after seeing the tool output
            continue

        # Otherwise treat as final assistant content
        content = msg.get("content")
        if content:
            final_answer = content.strip()
            break

        # Unexpected case
        print("LLM response did not contain function_call or content", file=sys.stderr)
        sys.exit(1)

    # Determine source: prefer last read_file call path if present
    source = ""
    for c in reversed(tool_calls):
        if c.get("tool") == "read_file":
            p = c.get("args", {}).get("path")
            if p:
                source = p
                break

    if final_answer is None:
        print("No final answer produced by LLM", file=sys.stderr)
        sys.exit(1)

    output = {"answer": final_answer, "source": source, "tool_calls": tool_calls}

    # Only print one JSON line to stdout
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
