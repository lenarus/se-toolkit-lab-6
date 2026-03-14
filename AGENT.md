# Agent — README

What this agent does
- agent.py is a minimal CLI that sends a single user question to an OpenAI-compatible chat completions API (Qwen Code in my setup) and prints exactly one JSON line to stdout:
  {"answer": "...", "tool_calls": []}
- No tools or agentic loop yet — just input → LLM → structured JSON output.

Chosen LLM provider and model
- Provider: Qwen Code API (self-hosted endpoint).
- Model: coder-model (configured via environment).

Configuration
1. Copy the example env file:
   cp .env.agent.example .env.agent.secret
2. Edit .env.agent.secret and set:
   - LLM_API_KEY — your provider API key
   - LLM_API_BASE — base URL for the chat completions endpoint (e.g. http://10.93.25.199:42005/v1/chat/completions)
   - LLM_MODEL — model name (e.g. coder-model)

Behavior and constraints
- Only valid JSON is printed to stdout. All logs, errors and debug go to stderr.
- Output schema (single JSON line):
  - answer: string (assistant reply)
  - tool_calls: list (empty for Task 1)
- The program enforces a ~60s timeout for the LLM request.
- Exit code 0 on success; non-zero on failure.

Requirements
- Python 3
- requests library: pip install requests

Run examples
- Run via Python:
  python3 agent.py "What does REST stand for?"
- Or using the project runner used in the lab:
  uv run agent.py "What does REST stand for?"
- Example stdout:
  {"answer":"Representational State Transfer.","tool_calls":[]}

Testing
- A regression test runs agent.py as a subprocess, parses stdout JSON, and asserts presence and types of `answer` and `tool_calls`.

Notes
- Keep your API key private; do not commit .env.agent.secret to version control.
- The system prompt is minimal for Task 1 and will be expanded in later tasks when tools and domain knowledge