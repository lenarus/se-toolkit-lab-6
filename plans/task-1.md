# Plan: Task 1 — Call an LLM from Code

Goal
- Build a small Python CLI (`agent.py`) that accepts a single question arg, calls the Qwen Code API, and prints exactly one JSON line to stdout:
  {"answer": "...", "tool_calls": []}

Chosen LLM provider and model
- Provider: Qwen Code API (self-hosted or remote endpoint).
- Model: `coder-model` (matches provided curl example). This will be configurable via `.env.agent.secret` as `LLM_MODEL`.

Credentials and configuration
- Configuration file: `.env.agent.secret` (copy from `.env.agent.example`).
- Required vars: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`.
- `agent.py` will read these env vars at runtime (no hardcoding).

High-level agent structure
1. Parse command-line args (first positional arg = question). If missing, print usage to stderr and exit non-zero.
2. Build chat request:
   - Minimal system prompt (e.g. "You are a helpful assistant. Answer concisely.").
   - Single user message with the question.
3. Send HTTP POST to `${LLM_API_BASE}/v1/chat/completions` with Authorization: Bearer `${LLM_API_KEY}` and JSON body `{ "model": LLM_MODEL, "messages": [...] }`.
   - Use a request timeout under 60s (e.g. 55s).
   - Print request/response debug only to stderr.
4. Parse LLM response:
   - Extract assistant text from `choices[0].message.content`.
   - If extraction fails, treat as error (write helpful message to stderr) and exit non-zero.
5. Produce final output on stdout as a single JSON line with required fields:
   - `answer` (string)
   - `tool_calls` (empty array for Task 1)
6. Exit 0 on success.

Error handling and constraints
- All debug/progress goes to stderr only.
- Only valid JSON on stdout.
- Respect the 60s runtime constraint (use request timeout + overall checks).
- Fail fast and return non-zero if LLM request fails or returned format is unexpected.

Tests and docs
- Add one regression test that runs `agent.py` as a subprocess, parses stdout JSON, and asserts presence of `answer` (string) and `tool_calls` (list).
- Add `AGENT.md` describing how to configure `.env.agent.secret`, run the CLI and the chosen model/provider.

Files to add
- lab/plans/task-1.md (this file)
- agent.py (project root)
- AGENT.md (project root)
- tests/test_agent_cli.py (one test)

Notes
- Use standard Python libs + `requests` (or stdlib `urllib.request`) to avoid heavy deps.
- Keep implementation minimal and robust; augment prompts and tools in
- fixing branch