# Agent — README

What this agent does
- agent.py is a CLI that accepts a question, interacts with an LLM, may call repository-inspection tools, call the running backend, and prints exactly one JSON line to stdout:
  {"answer":"...","source":"...","tool_calls":[...]}

LLM provider and config
- Provider: Qwen Code API (OpenAI-compatible). Model configurable via `.env.agent.secret`:
  - LLM_API_KEY
  - LLM_API_BASE (base URL)
  - LLM_MODEL
- Requests timeout ~55s; CLI aims to finish within 60s.

Tools (function-calling schemas)
- list_files(path): list entries at a relative directory (returns newline-separated names).
  - Parameters: path (string) — relative directory path from project root (no `..`).
- read_file(path): return file contents (text), truncated if too large.
  - Parameters: path (string) — relative file path from project root (no `..`).
- query_api(method, path, body): call the running backend for runtime facts and data queries.
  - Parameters:
    - method (string): HTTP method, e.g. GET, POST.
    - path (string): path on the backend starting with `/` (no scheme/host).
    - body (string, optional): JSON string for request body.
  - Returns: JSON-stringified object with at least {"status_code": int, "body": "<response text>"} (truncated if large).

Authentication for query_api
- The agent uses `LMS_API_KEY` (from environment, typically .env.docker.secret) to authenticate backend requests.
- If `LMS_API_KEY` is present the agent sets header `Authorization: Bearer <LMS_API_KEY>`.
- Backend base URL is read from `AGENT_API_BASE_URL` (defaults to http://localhost:42002). Paths passed to query_api must begin with `/` and must not contain an external host or scheme.

How the LLM should decide between tools
- Heuristics encoded in the system prompt:
  - Use `list_files` and `read_file` when the answer requires inspecting repository files, docs, or source code.
  - Use `query_api` for runtime/system facts or data-dependent queries (counts, current status, live endpoints).
  - Prefer `query_api` for anything that needs current state (database counts, live status codes, feature flags).
  - Always emit function calls that match the supplied schemas. When done, return a concise answer and include `Source: <path>` or `Source: api:<path>`.

Agentic loop behavior
- The agent sends the user question, system prompt, and function schemas to the LLM.
- If the LLM issues a function call, the agent executes the tool, appends a `tool` message with the result, and repeats.
- The loop stops when the LLM returns assistant content or after 10 tool calls.
- All tool results are recorded in `tool_calls` in the final JSON.

Lessons learned from local benchmark (initial run)
- Initial local benchmark (single pass, mocked LLM/backends) produced a low baseline score (initial run: 3/10).
- First failures observed:
  - Missing or miswired backend auth caused query_api calls to return 401/403.
  - Path handling allowed malformed values; added strict validation to reject schemes/hosts and require leading `/`.
  - Large file truncation removed context needed by the model; improved truncation notes and returned first/last segments.
  - Tool result formatting varied; standardized query_api to always return JSON with `status_code` and `body`.
- Iterations applied:
  - Added Authorization header wiring using `LMS_API_KEY`.
  - Hardened path sanitization and validation.
  - Increased clarity in the system prompt with explicit examples mapping question → tool.
  - Standardized tool outputs (JSON string) so the LLM can reliably parse results.

Final evaluation score
- Final score: N/A (benchmark was not executed by this process). The initial local test run noted above was 3/10. To obtain a final score:
  1. Ensure `.env.agent.secret` and `.env.docker.secret` are configured with LLM and backend keys.
  2. Run the local benchmark runner or `run_eval.py` (project-specific).
  3. Inspect failures and iterate using the lessons above; common fixes are auth, prompt examples, and truncation handling.

How to re-run the benchmark locally
- Install deps: `python3 -m venv .venv && source .venv/bin/activate && pip install -U pip requests uv pytest`
- Ensure environment:
  - Copy and edit `.env.agent.secret` (LLM_API_KEY, LLM_API_BASE, LLM_MODEL).
  - Ensure `.env.docker.secret` (or env) contains `LMS_API_KEY` and set `AGENT_API_BASE_URL` if backend is not on default.
- Run agent manually or run the provided benchmark/eval script in the repo.
- Inspect failing cases, update system prompt or tool behavior, and re-run until satisfied.

Notes
- Only valid JSON is printed to stdout; all debug/logs go to stderr.
- Keep API keys private and do not commit secrets to version control.