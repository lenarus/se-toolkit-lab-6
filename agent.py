#!/usr/bin/env python3
import os
import sys
import json
import pathlib
import re
import logging
import os

try:
    import requests
except Exception:
    print(
        "Missing dependency: requests. Install with: pip install requests",
        file=sys.stderr,
    )
    sys.exit(1)


# configure logger early in main (or module top)
logger = logging.getLogger("agent")
if os.environ.get("AGENT_DEBUG"):
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
else:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _sanitize_payload_for_log(payload):
    try:
        p = json.loads(json.dumps(payload))  # deep copy-ish
    except Exception:
        return "<unserializable payload>"
    # truncate long message contents
    for m in p.get("messages", []):
        if isinstance(m, dict) and "content" in m and isinstance(m["content"], str):
            if len(m["content"]) > 500:
                m["content"] = m["content"][:500] + "...(truncated)"
    # remove or mask functions if desired
    if "functions" in p:
        p["functions"] = "[functions omitted]"
    return json.dumps(p, ensure_ascii=False)


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


# New: query_api implementation
def query_api_impl(
    method: str, path: str, body: str | None, include_auth: bool = True
) -> str:
    # Configuration from environment
    base = os.environ.get("AGENT_API_BASE_URL", "http://10.93.25.199:42002")
    lms_key = os.environ.get("LMS_API_KEY")

    # Basic sanitization
    if not path or not isinstance(path, str) or not path.startswith("/"):
        return f"ERROR: invalid path '{path}' (must start with '/')"
    if "http://" in path or "https://" in path:
        return (
            f"ERROR: invalid path '{path}' (must be a relative path starting with '/')"
        )

    method_up = (method or "GET").upper()
    allowed = {"GET", "POST", "PUT", "DELETE", "PATCH"}
    if method_up not in allowed:
        return f"ERROR: unsupported method '{method_up}'"

    url = base.rstrip("/") + path

    headers = {}
    if body:
        headers["Content-Type"] = "application/json"
    if include_auth and lms_key:
        headers["Authorization"] = f"Bearer {lms_key}"

    try:
        resp = requests.request(
            method_up,
            url,
            headers=headers,
            data=body.encode("utf-8") if body else None,
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return json.dumps(
            {"status_code": 0, "body": f"ERROR: request failed: {e}"},
            ensure_ascii=False,
        )

    # Try to decode/format body
    max_bytes = 200 * 1024
    try:
        # Prefer JSON body if present
        ct = resp.headers.get("Content-Type", "")
        if "application/json" in ct:
            try:
                body_obj = resp.json()
                body_str = json.dumps(body_obj, ensure_ascii=False)
            except Exception:
                body_str = resp.text
        else:
            body_str = resp.text
    except Exception:
        body_str = "<unable to decode body>"

    truncated = False
    if isinstance(body_str, str) and len(body_str.encode("utf-8")) > max_bytes:
        # truncate to max_bytes safely
        b = body_str.encode("utf-8")[:max_bytes]
        try:
            body_str = b.decode("utf-8", errors="replace")
        except Exception:
            body_str = b.decode("latin-1", errors="replace")
        truncated = True

    if truncated:
        body_str = "(TRUNCATED) " + body_str

    result = {"status_code": resp.status_code, "body": body_str}
    return json.dumps(result, ensure_ascii=False)


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
        {
            "name": "query_api",
            "description": "Send an HTTP request to the project backend. Use for runtime/system facts and data-dependent queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method, e.g. GET, POST",
                    },
                    "path": {
                        "type": "string",
                        "description": "Absolute path on backend starting with '/', e.g. /items/",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON string payload for POST/PUT requests",
                    },
                    "include_auth": {
                        "type": "boolean",
                        "description": "Whether to include LMS_API_KEY header (default true). Set to false to test unauthenticated access.",
                    },
                },
                "required": ["method", "path"],
            },
        },
    ]

    system_prompt = (
        "You are a helpful assistant that can inspect the repository using two tools: "
        "list_files(path) and read_file(path), and query runtime backend state using query_api(method, path, body, include_auth). "
        "Use list_files to discover files and read_file to read file contents. Use query_api for runtime facts "
        "(counts, current status, endpoints). IMPORTANT: When you want to use a tool, emit a proper function call using the declared schema - do NOT write XML or text-based tool calls. "
        "Examples: if you need the number of items call query_api(method='GET', path='/items/'). "
        "When the question asks about unauthenticated access or requests without headers, you MUST set include_auth=false in your query_api call. "
        "When finished, return a concise answer and include the source as 'Source: <path>' or 'Source: api:<path>' where appropriate."
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

        # DEBUG: dump payload to stderr before sending
        logger.debug("REQUEST PAYLOAD: %s", _sanitize_payload_for_log(payload))

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=55)
        except requests.exceptions.RequestException as e:
            logger.error("LLM request failed: %s", e)
            sys.exit(1)

        logger.debug("RESPONSE STATUS: %s", resp.status_code)
        # log truncated body only
        logger.debug(
            "RESPONSE BODY: %s",
            resp.text[:2000].replace(os.environ.get("LLM_API_KEY", ""), "[REDACTED]"),
        )

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

        # Handle both function_call and tool_calls formats (Qwen)
        function_call = msg.get("function_call")
        tool_calls_raw = msg.get("tool_calls")
        if (
            tool_calls_raw
            and isinstance(tool_calls_raw, list)
            and len(tool_calls_raw) > 0
        ):
            tc = tool_calls_raw[0]
            if isinstance(tc, dict):
                func_info = tc.get("function", {})
                if func_info:
                    function_call = {
                        "name": func_info.get("name"),
                        "arguments": func_info.get("arguments", "{}"),
                    }
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
            elif name == "query_api":
                method = args.get("method", "GET")
                path_arg = args.get("path", "")
                body = args.get("body")
                include_auth = args.get("include_auth", True)
                # validate and execute
                result = query_api_impl(method, path_arg, body, include_auth)
            else:
                result = f"ERROR: unknown tool {name}"

            # Record the tool call
            tool_calls.append({"tool": name, "args": args, "result": result})

            # Qwen-compatible: assistant declares tool_calls first
            declared = {"function": {"name": name, "arguments": args}}
            messages.append({"role": "assistant", "tool_calls": [declared]})
            messages.append({"role": "tool", "name": name, "content": result})
            # Continue the loop so the model can respond after seeing the tool output
            continue

        # Otherwise treat as final assistant content
        content = msg.get("content")
        if content:
            # Strip markdown code blocks if present
            content_stripped = content.strip()
            if content_stripped.startswith("```json"):
                content_stripped = content_stripped[7:]
            elif content_stripped.startswith("```"):
                content_stripped = content_stripped[3:]
            if content_stripped.endswith("```"):
                content_stripped = content_stripped[:-3]
            content_stripped = content_stripped.strip()

            # Handle provider that returns function_call embedded as JSON string in content
            try:
                parsed = json.loads(content_stripped)
                if isinstance(parsed, dict) and "function_call" in parsed:
                    fc = parsed["function_call"]
                    name = fc.get("name")
                    args_text = fc.get("arguments", "{}")
                    try:
                        args = (
                            json.loads(args_text)
                            if isinstance(args_text, str)
                            else args_text
                        )
                    except Exception:
                        args = {}
                    # execute same as function_call branch
                    if name == "read_file":
                        path_arg = args.get("path", "")
                        result = read_file_impl(project_root, path_arg)
                    elif name == "list_files":
                        path_arg = args.get("path", "")
                        result = list_files_impl(project_root, path_arg)
                    elif name == "query_api":
                        method = args.get("method", "GET")
                        path_arg = args.get("path", "")
                        body = args.get("body")
                        include_auth = args.get("include_auth", True)
                        result = query_api_impl(method, path_arg, body, include_auth)
                    else:
                        result = f"ERROR: unknown tool {name}"
                    call_count += 1
                    tool_calls.append({"tool": name, "args": args, "result": result})
                    declared = {"function": {"name": name, "arguments": args}}
                    messages.append({"role": "assistant", "tool_calls": [declared]})
                    messages.append({"role": "tool", "name": name, "content": result})
                    continue
                # Handle direct JSON object with query_api fields (e.g., {"method": ..., "path": ...})
                if (
                    isinstance(parsed, dict)
                    and "path" in parsed
                    and parsed.get("path", "").startswith("/")
                ):
                    name = "query_api"
                    method = parsed.get("method", "GET")
                    path = parsed.get("path", "")
                    body = parsed.get("body")
                    include_auth = parsed.get("include_auth", True)
                    result = query_api_impl(method, path, body, include_auth)
                    args = {
                        "method": method,
                        "path": path,
                        "body": body,
                        "include_auth": include_auth,
                    }
                    call_count += 1
                    tool_calls.append({"tool": name, "args": args, "result": result})
                    declared = {"function": {"name": name, "arguments": args}}
                    messages.append({"role": "assistant", "tool_calls": [declared]})
                    messages.append({"role": "tool", "name": name, "content": result})
                    continue
            except Exception:
                # not JSON or malformed — fall through to other fallbacks
                pass

            # Fallback: XML-style function calls
            # Format 1: <function_call>\n<name>...</name>\n<arguments>...</arguments>\n</function_call>
            xml_match = re.search(
                r"<function_call>.*?<name>([^<]+)</name>.*?<arguments>([^<]+)</arguments>.*?</function_call>",
                content,
                re.DOTALL,
            )
            if xml_match:
                name = xml_match.group(1).strip()
                args_text = xml_match.group(2).strip()
                try:
                    args = json.loads(args_text) if args_text else {}
                except Exception:
                    args = {}
                result = execute_tool(name, args, project_root)
                call_count += 1
                tool_calls.append({"tool": name, "args": args, "result": result})
                declared = {"function": {"name": name, "arguments": args}}
                messages.append({"role": "assistant", "tool_calls": [declared]})
                messages.append({"role": "tool", "name": name, "content": result})

            # Format 2: <function name="list_files">
            # <parameter name="path">...</parameter>
            # </function>
            func_match = re.search(
                r'<function name="([^"]+)">.*?<parameter name="path">([^<]+)</parameter>.*?</function>',
                content,
                re.DOTALL,
            )
            if func_match:
                name = func_match.group(1).strip()
                path = func_match.group(2).strip()
                args = {"path": path}
                # Execute the tool based on name
                if name == "read_file":
                    result = read_file_impl(project_root, path)
                elif name == "list_files":
                    result = list_files_impl(project_root, path)
                elif name == "query_api":
                    result = query_api_impl("GET", path, None)
                else:
                    result = f"ERROR: unknown tool {name}"
                call_count += 1
                tool_calls.append({"tool": name, "args": args, "result": result})
                declared = {"function": {"name": name, "arguments": args}}
                messages.append({"role": "assistant", "tool_calls": [declared]})
                messages.append({"role": "tool", "name": name, "content": result})
                continue

            # Fallback: if the model emitted a pseudo-tool call as text like:
            #   list_files(path='wiki')  or  read_file("wiki/git-workflow.md")
            m = re.match(
                r"^\s*(?P<name>list_files|read_file|query_api)\s*\(\s*(?P<args>.*)\s*\)\s*$",
                content.strip(),
            )
            if m:
                name = m.group("name")
                args_text = m.group("args").strip()
                # try to extract a simple "path='...'" or a single quoted arg
                path_arg = ""
                body_arg = None
                # key=value style
                kp = re.search(r"path\s*=\s*['\"](?P<p>[^'\"]+)['\"]", args_text)
                if kp:
                    path_arg = kp.group("p")
                else:
                    # single quoted positional arg
                    kp2 = re.match(r"^['\"](?P<p>[^'\"]+)['\"]$", args_text)
                    if kp2:
                        path_arg = kp2.group("p")
                # body for query_api: look for body=...
                kb = re.search(r"body\s*=\s*(?P<b>.+)$", args_text)
                if kb:
                    body_raw = kb.group("b").strip()
                    # try to strip surrounding quotes
                    if (body_raw.startswith("'") and body_raw.endswith("'")) or (
                        body_raw.startswith('"') and body_raw.endswith('"')
                    ):
                        body_arg = body_raw[1:-1]
                    else:
                        body_arg = body_raw

                # execute the tool similarly to function_call branch
                if name == "read_file":
                    result = read_file_impl(project_root, path_arg)
                elif name == "list_files":
                    result = list_files_impl(project_root, path_arg)
                elif name == "query_api":
                    # allow method default GET if not provided
                    method_m = re.search(
                        r"method\s*=\s*['\"](?P<m>[^'\"]+)['\"]", args_text
                    )
                    method = method_m.group("m") if method_m else "GET"
                    include_auth_m = re.search(
                        r"include_auth\s*=\s*(?P<ia>True|False)", args_text
                    )
                    include_auth = (
                        include_auth_m.group("ia") == "True" if include_auth_m else True
                    )
                    result = query_api_impl(method, path_arg, body_arg, include_auth)
                else:
                    result = f"ERROR: unknown tool {name}"

                call_count += 1
                tool_calls.append(
                    {
                        "tool": name,
                        "args": {"path": path_arg, "body": body_arg}
                        if name == "query_api"
                        else {"path": path_arg},
                        "result": result,
                    }
                )
                declared_args = (
                    {"path": path_arg, "body": body_arg}
                    if name == "query_api"
                    else {"path": path_arg}
                )
                declared = {"function": {"name": name, "arguments": declared_args}}
                messages.append({"role": "assistant", "tool_calls": [declared]})
                messages.append({"role": "tool", "name": name, "content": result})
                # continue the loop so the model can respond after seeing the tool output
                continue

            # Otherwise treat as final text answer
            final_answer = content.strip()
            break

        # Unexpected case
        print("LLM response did not contain function_call or content", file=sys.stderr)
        sys.exit(1)

    # Determine source: prefer last read_file call path if present, else api path
    source = ""
    for c in reversed(tool_calls):
        if c.get("tool") == "read_file":
            p = c.get("args", {}).get("path")
            if p:
                source = p
                break
        if c.get("tool") == "query_api" and not source:
            p = c.get("args", {}).get("path")
            if p:
                source = f"api:{p}"
                # don't break yet in case a later read_file exists

    if final_answer is None:
        print("No final answer produced by LLM", file=sys.stderr)
        sys.exit(1)

    output = {"answer": final_answer, "source": source, "tool_calls": tool_calls}

    # Only print one JSON line to stdout
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
