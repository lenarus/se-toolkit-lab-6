# Agent — README

What this agent does
- agent.py is a CLI that accepts a question, interacts with an LLM, may call repository-inspection tools, and prints exactly one JSON line to stdout:
  {"answer":"...","source":"...","tool_calls":[...]}

LLM provider and config
- Provider: Qwen Code API (OpenAI-compatible). Model configurable via `.env.agent.secret`:
  - LLM_API_KEY
  - LLM_API_BASE (base URL, e.g. http://10.93.25.199:42005/v1)
  - LLM_MODEL (e.g. coder-model)
- Requests timeout ~55s; CLI aims to finish within 60s.

Tools (function-calling schemas)
- list_files(path): list entries at a relative directory (returns newline-separated names).
  - Parameters: path (string) — relative directory path from project root (no `..`).
- read_file(path): return file contents (text), truncated if too large.
  - Parameters: path (string) — relative file path from project root (no `..`).
- Tool results are returned to the LLM as messages and recorded in `tool_calls` in the final JSON.

Agentic loop
1. Compose chat request with:
   - system prompt (see below),
   - user question,
   - function schemas for `list_files` and `read_file`,
   - function_call: "auto".
2. If the model issues a function call:
   - agent executes the requested tool locally (with path security checks),
   - appends a tool-role message containing the result,
   - resends the conversation to the LLM.
3. Repeat until the model returns assistant content (final answer) or 10 tool calls are reached.
4. Final stdout is one JSON line:
   {
     "answer": "<final text>",
     "source": "<most relevant file path or empty>",
     "tool_calls": [
       {"tool":"list_files","args":{"path":"wiki"},"result":"..."},
       {"tool":"read_file","args":{"path":"wiki/git-workflow.md"},"result":"..."}
     ]
   }

System prompt strategy
- Instruct the model to:
  - Prefer using `list_files` to discover files and `read_file` to inspect content.
  - Produce function calls that match the provided schemas.
  - When finished, return a concise answer and include a `Source: <path>` (the file path answering the question).
  - Keep responses concise and factual.

Security and path handling
- Paths must be relative and inside the project root. Requests containing `..` or absolute paths are rejected.
- Implementation resolves and verifies paths against the project root to prevent directory traversal.
- read_file truncates large files (e.g., >200 KiB) and reports truncation.
- list_files limits entries returned (e.g., first 500).

Behavior & constraints
- Only valid JSON printed to stdout; all debug/logs to stderr.
- Max 10 tool calls per question.
- Exit code 0 on success, non-zero on failure.

Running
- Prepare env: cp .env.agent.example .env.agent.secret and edit values.
- Install deps: pip install requests
- Run:
  - python3 agent.py "What does REST stand for?"
  - or uv run agent.py "What does REST stand for?"

Testing
- Tests mock the LLM with a local HTTP server and assert the final JSON contains `answer`, `source`,