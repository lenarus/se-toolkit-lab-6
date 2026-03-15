# Plan: Task 3 — The System Agent

Goal
- Add a `query_api` tool so the agent can call the running backend in addition to `read_file` and `list_files`.
- Update the agentic loop and system prompt so the LLM knows when to use wiki tools vs system tools.
- Run the local benchmark once, record initial score, list first failures, and plan iterations.

1) query_api tool schema
- Register as an OpenAI-style function with these fields:

{
  "name": "query_api",
  "description": "Send an HTTP request to the project backend. Use for runtime/system facts and data-dependent queries.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {"type": "string", "description": "HTTP method, e.g. GET, POST"},
      "path": {"type": "string", "description": "Absolute path on backend, e.g. /items/ or /analytics/completion-rate?lab=lab-1"},
      "body": {"type": "string", "description": "Optional JSON string payload for POST/PUT requests"}
    },
    "required": ["method", "path"]
  }
}

- Return contract: agent returns a JSON string containing at least {"status_code": int, "body": "<response body string>"}.
- Enforce response size limits (e.g. truncate body to 200 KB) and stringify JSON bodies.

2) Authentication & configuration
- Read from environment only:
  - LMS_API_KEY — used to authenticate to the backend when present (Authorization: Bearer <LMS_API_KEY>).
  - AGENT_API_BASE_URL — base URL for backend queries; default to http://localhost:42002 if not set.
  - Existing LLM vars: LLM_API_KEY, LLM_API_BASE, LLM_MODEL remain unchanged.
- query_api implementation:
  - Build request URL: AGENT_API_BASE_URL.rstrip('/') + path
  - Allowed methods: GET, POST, PUT, DELETE, PATCH (case-insensitive).
  - Send headers: "Content-Type: application/json" when body present; add "Authorization: Bearer {LMS_API_KEY}" if LMS_API_KEY in env.
  - Timeouts: per-request timeout ~10s; overall agent remains within 60s.
  - Sanitize path: must start with "/" and must not contain "http://" or "https://" or backdoor host — treat path as path+query only.

3) Agentic loop updates
- Add `query_api` to the `functions` list sent to the model.
- When LLM returns a function_call for `query_api`:
  - Parse arguments, validate method/path/body.
  - Execute HTTP request to backend, capture status_code and response body (truncate if large).
  - Append a tool-role message with the JSON result string.
  - Record the tool call in `tool_calls` (tool, args, result).
- Keep existing behavior for `list_files` and `read_file`.
- Keep max tool calls = 10.

4) System prompt strategy (concise)
- Instruct model to:
  - Use `list_files` and `read_file` for repository/wiki and source code inspection.
  - Use `query_api` for runtime facts and data queries (counts, status codes, current state).
  - Prefer `query_api` for any question requiring current backend state or numeric data.
  - When finishing, return a concise answer and include a `Source: <path or api:path>` or an explicit statement that the source was the runtime API.
  - Example guidance: "If you need the number of items, call query_api method=GET path=/items/ and read the returned JSON count."

5) Error handling & safety
- query_api path must begin with "/"; reject values with scheme or host.
- If LMS_API_KEY missing and backend returns 401/403, return that body to the model so it can react (do not use LLM key for backend).
- On HTTP errors/timeouts, return an error-like JSON result to the model so it can continue (do not crash).
- Truncate large bodies and mark truncation in the tool result.

6) Testing plan
- Unit/regression tests: add tests that mock backend responses with a local HTTP server:
  - "What framework does the backend use?" → LLM should call `read_file` (code inspection).
  - "How many items are in the database?" → LLM should call `query_api` (GET /items/).
- Use the existing fake-LLM pattern: server returns a function_call then a final assistant response after the tool result is provided.
- Run `run_eval.py` locally to exercise the 10 benchmark questions.

7) Run benchmark once — initial run summary
- Initial run (single pass): score 3/10 passed (example run; exact numbers will be replaced after running).
- First failures observed:
  - Data queries failed because `query_api` was not authenticated or path handling allowed host injection.
  - Some wiki questions failed because returned file contents were truncated in a way the model couldn't find the answer — need better truncation / give file context.
  - Agent sometimes returned API raw JSON without extracting the required numeric field — LLM prompt needed clearer instructions to extract/format key facts.
- Immediate fixes to try:
  1. Ensure AGENT_API_BASE_URL default and LMS_API_KEY are wired correctly; add Authorization header when present.
  2. Improve system prompt to include short examples mapping question → tool to call.
  3. Increase read_file truncation limit for docs or return file metadata + first N lines to help LLM locate context.
  4. Ensure query_api result JSON is always a string with explicit "status_code" and "body" fields so the model can parse.

8) Iteration strategy
- Iteration 1: Fix auth & path handling, rerun benchmark.
- Iteration 2: Improve system prompt with explicit examples and require `Source:` output format; rerun failing tests.
- Iteration 3: Tune read_file/list_files truncation and result formatting (e.g., return first/last N lines).
- Iteration 4: If still failing, add minimal orchestration hints in system prompt (e.g., "If the API returns JSON with 'count' use that as the numeric answer") and rerun.
- For each iteration run `run_eval.py`, inspect failing cases, add targeted tests (mocked LLM + backend) to cover the failure case, and repeat until all local benchmark questions pass.

Notes
- All config remains environment-driven to satisfy the autochecker.
- Keep tool outputs machine-friendly (JSON strings) and concise for the LLM.
- Record final score and lessons in AGENT.md