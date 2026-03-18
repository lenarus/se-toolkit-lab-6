# Plan: Task 2 — The Documentation Agent

Goal
- Extend the CLI agent to support two tools (read_file, list_files) and an agentic loop:
  - Send question + tool schemas to the LLM
  - If the LLM requests a tool call, execute it, return the result to the LLM, repeat
  - Stop when the LLM returns a final text answer or after 10 tool calls
- Final stdout: one JSON line with fields: `answer` (string), `source` (string), `tool_calls` (list)

LLM provider & model
- Continue using Qwen Code API (OpenAI-compatible chat completions).
- Default model: `coder-model` (configurable via .env.agent.secret LLM_MODEL).

Tool schemas (function-calling JSON schemas)
- Provide the LLM with OpenAI-style function schemas in the chat request so it can emit function calls.

1) list_files
{
  "name": "list_files",
  "description": "List files and directories at a given relative path under the project root. Return newline-separated entries.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative directory path from project root (no .. allowed)"}
    },
    "required": ["path"]
  }
}

2) read_file
{
  "name": "read_file",
  "description": "Read a text file from the project repository and return its contents. Path must be relative and inside project.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative file path from project root (no .. allowed)"}
    },
    "required": ["path"]
  }
}

Agentic loop design
1. Compose initial chat request:
   - system message: concise instructions that tell the model:
     - Use `list_files` to discover wiki files under `wiki` (or repo) and `read_file` to read content.
     - Always include a `source` (file path + optional anchor) in the final answer.
     - When calling a tool use the declared schema and return JSON args.
   - user message: the user's question.
   - functions: the two schemas above.
   - function_call: "auto" (allow model to select).

2. Send POST to ${LLM_API_BASE}/v1/chat/completions (timeout ~55s).

3. Inspect response:
   - If choices[0].message contains a `function_call` object:
     - Extract name and JSON-parse `arguments`.
     - Record the planned tool call in an in-memory `tool_calls` list (store tool, args).
     - Execute the corresponding local Python function (safe implementation; see security).
     - Create a new message with role "tool", name equal to the function name, and content the tool result (string).
     - Append the tool result to the messages list and repeat the loop (resend messages).
   - Else if choices[0].message.content is present:
     - Treat this as final assistant answer. Extract text and any source instruction.
     - Stop loop and produce final JSON.

4. Loop limits and exit:
   - Max 10 tool calls per request. If exceeded, stop and let the LLM know (return partial answer with note).
   - If any LLM response is malformed, return an error on stderr and exit non-zero.

Tool implementation & security
- Project root: resolved via os.path.dirname(os.path.abspath(__file__)).
- Normalize and validate paths:
  - Use pathlib.Path(project_root) / Path(path).resolve()?
  - Reject requests containing ".." or absolute paths.
  - After joining, ensure resolved path is within the project root (pathlib.Path.resolve and check .is_relative_to or string prefix).
- read_file:
  - If file not found return a concise error string (e.g., "ERROR: not found: {path}").
  - Limit read size (e.g., 200 KiB). If larger, return trimmed content with a note.
  - Return text; non-text fallback to a message.
- list_files:
  - Validate directory exists and is within project root.
  - Return newline-separated names (files and directories).
  - For large directories, limit entries (e.g., first 500 lines) and indicate truncation.

Message bookkeeping
- Maintain a message list starting from system and user messages.
- After each tool execution append:
  - {"role":"tool","name":"<tool>","content":"<result>"}
- This mirrors the OpenAI function-calling flow and lets the model reason about tool outputs.

Output schema
- On success print exactly one JSON line to stdout:
  {
    "answer": "<final answer string>",
    "source": "<file path or file#anchor>",
    "tool_calls": [
      {"tool":"list_files","args":{"path":"wiki"},"result":"..."},
      {"tool":"read_file","args":{"path":"wiki/git-workflow.md"},"result":"..."}
    ]
  }
- All logs, debug, and LLM request/response dumps go to stderr only.

Error handling & timeouts
- Per-request timeout ~55s; overall CLI should aim to complete under 60s.
- If network or parsing errors occur, print a helpful message to stderr and exit non-zero.
- If an invalid tool request is received (bad args), return an error string to the LLM and continue/stop as appropriate.

Testing plan
- Unit/regression tests will mock an LLM by running a local HTTP server that returns predetermined function-call responses.
- Tests to add:
  1. "How do you resolve a merge conflict?" — expect at least one read_file call; final `source` contains `wiki/git-workflow.md`.
  2. "What files are in the wiki?" — expect list_files to be called and listed in `tool_calls`.
- Reuse the existing fake-server pattern from Task 1 tests to return function_call payloads and then assistant final answers after tool results are injected.

Implementation steps (order)
1. Commit this plan as plans/task-2.md.
2. Update agent.py:
   - add function schemas in requests,
   - implement read_file and list_files with security checks,
   - implement the loop described above and final JSON output.
3. Update AGENT.md with tool docs and system prompt strategy.
4. Add the two tests and run them locally (pytest or uv run pytest).
5. Iterate on edge-cases (file size, path validation, truncation).

Notes
- Keep tool results succinct but complete; prefer returning full file content where safe.
- The system prompt must instruct the model to always prefer using tools for repository access and to include a precise `source` in the final answer.
- Ensure deterministic behavior for tests by mocking the LLM responses.
```// filepath: /home/lenarus/Projects/se-toolkit-lab-6/plans/task-2.md
# Plan: Task 2 — The Documentation Agent

Goal
- Extend the CLI agent to support two tools (read_file, list_files) and an agentic loop:
  - Send question + tool schemas to the LLM
  - If the LLM requests a tool call, execute it, return the result to the LLM, repeat
  - Stop when the LLM returns a final text answer or after 10 tool calls
- Final stdout: one JSON line with fields: `answer` (string), `source` (string), `tool_calls` (list)

LLM provider & model
- Continue using Qwen Code API (OpenAI-compatible chat completions).
- Default model: `coder-model` (configurable via .env.agent.secret LLM_MODEL).

Tool schemas (function-calling JSON schemas)
- Provide the LLM with OpenAI-style function schemas in the chat request so it can emit function calls.

1) list_files
{
  "name": "list_files",
  "description": "List files and directories at a given relative path under the project root. Return newline-separated entries.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative directory path from project root (no .. allowed)"}
    },
    "required": ["path"]
  }
}

2) read_file
{
  "name": "read_file",
  "description": "Read a text file from the project repository and return its contents. Path must be relative and inside project.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative file path from project root (no .. allowed)"}
    },
    "required": ["path"]
  }
}

Agentic loop design
1. Compose initial chat request:
   - system message: concise instructions that tell the model:
     - Use `list_files` to discover wiki files under `wiki` (or repo) and `read_file` to read content.
     - Always include a `source` (file path + optional anchor) in the final answer.
     - When calling a tool use the declared schema and return JSON args.
   - user message: the user's question.
   - functions: the two schemas above.
   - function_call: "auto" (allow model to select).

2. Send POST to ${LLM_API_BASE}/v1/chat/completions (timeout ~55s).

3. Inspect response:
   - If choices[0].message contains a `function_call` object:
     - Extract name and JSON-parse `arguments`.
     - Record the planned tool call in an in-memory `tool_calls` list (store tool, args).
     - Execute the corresponding local Python function (safe implementation; see security).
     - Create a new message with role "tool", name equal to the function name, and content the tool result (string).
     - Append the tool result to the messages list and repeat the loop (resend messages).
   - Else if choices[0].message.content is present:
     - Treat this as final assistant answer. Extract text and any source instruction.
     - Stop loop and produce final JSON.

4. Loop limits and exit:
   - Max 10 tool calls per request. If exceeded, stop and let the LLM know (return partial answer with note).
   - If any LLM response is malformed, return an error on stderr and exit non-zero.

Tool implementation & security
- Project root: resolved via os.path.dirname(os.path.abspath(__file__)).
- Normalize and validate paths:
  - Use pathlib.Path(project_root) / Path(path).resolve()?
  - Reject requests containing ".." or absolute paths.
  - After joining, ensure resolved path is within the project root (pathlib.Path.resolve and check .is_relative_to or string prefix).
- read_file:
  - If file not found return a concise error string (e.g., "ERROR: not found: {path}").
  - Limit read size (e.g., 200 KiB). If larger, return trimmed content with a note.
  - Return text; non-text fallback to a message.
- list_files:
  - Validate directory exists and is within project root.
  - Return newline-separated names (files and directories).
  - For large directories, limit entries (e.g., first 500 lines) and indicate truncation.

Message bookkeeping
- Maintain a message list starting from system and user messages.
- After each tool execution append:
  - {"role":"tool","name":"<tool>","content":"<result>"}
- This mirrors the OpenAI function-calling flow and lets the model reason about tool outputs.

Output schema
- On success print exactly one JSON line to stdout:
  {
    "answer": "<final answer string>",
    "source": "<file path or file#anchor>",
    "tool_calls": [
      {"tool":"list_files","args":{"path":"wiki"},"result":"..."},
      {"tool":"read_file","args":{"path":"wiki/git-workflow.md"},"result":"..."}
    ]
  }
- All logs, debug, and LLM request/response dumps go to stderr only.

Error handling & timeouts
- Per-request timeout ~55s; overall CLI should aim to complete under 60s.
- If network or parsing errors occur, print a helpful message to stderr and exit non-zero.
- If an invalid tool request is received (bad args), return an error string to the LLM and continue/stop as appropriate.

Testing plan
- Unit/regression tests will mock an LLM by running a local HTTP server that returns predetermined function-call responses.
- Tests to add:
  1. "How do you resolve a merge conflict?" — expect at least one read_file call; final `source` contains `wiki/git-workflow.md`.
  2. "What files are in the wiki?" — expect list_files to be called and listed in `tool_calls`.
- Reuse the existing fake-server pattern from Task 1 tests to return function_call payloads and then assistant final answers after tool results are injected.

Implementation steps (order)
1. Commit this plan as plans/task-2.md.
2. Update agent.py:
   - add function schemas in requests,
   - implement read_file and list_files with security checks,
   - implement the loop described above and final JSON output.
3. Update AGENT.md with tool docs and system prompt strategy.
4. Add the two tests and run them locally (pytest or uv run pytest).
5. Iterate on edge-cases (file size, path validation, truncation).

Notes
- Keep tool results succinct but complete; prefer returning full file content where safe.
- The system prompt must instruct the model to always prefer using tools for repository access and to include a precise `source` in the final answer.
- Ensure deterministic behavior for tests by mocking the LLM responses.