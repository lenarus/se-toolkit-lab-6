# The System Agent

In Task 2 you built an agent that reads documentation. But documentation can be outdated — the real system is the source of truth. In this task you will give your agent a new tool (`query_api`) so it can talk to your deployed backend, and teach it to answer two new kinds of questions: static system facts (framework, ports, status codes) and data-dependent queries (item count, scores).

## What you will build

You will add a `query_api` tool to the agent you built in Task 2. The agentic loop stays the same — you are just adding one more tool the LLM can call. The agent can now reach your deployed backend in addition to reading files.

## CLI interface

Same rules as Task 2. The only change: `source` is now optional (system questions may not have a wiki source).

```bash
uv run agent.py "How many items are in the database?"
```

```json
{
  "answer": "There are 120 items in the database.",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, ...}"}
  ]
}
```

## New tool: `query_api`

Call your deployed backend API. Register it as a function-calling schema alongside your existing tools.

- **Parameters:** `method` (string — GET, POST, etc.), `path` (string — e.g., `/items/`), `body` (string, optional — JSON request body).
- **Returns:** JSON string with `status_code` and `body`.
- **Authentication:** use `LMS_API_KEY` from `.env.docker.secret` (the backend key, not the LLM key).

Update your system prompt so the LLM knows when to use wiki tools vs `query_api` vs `read_file` on source code.

> **Note:** Two distinct keys: `LMS_API_KEY` (in `.env.docker.secret`) protects your backend endpoints. `LLM_API_KEY` (in `.env.agent.secret`) authenticates with your LLM provider. Don't mix them up.

## Deliverables

### 1. Plan (`plans/task-3.md`)

Before writing code, create `plans/task-3.md`. Describe how you will define the `query_api` tool schema, handle authentication, and update the system prompt.

### 2. Tool and agent updates (update `agent.py`)

Add `query_api` as a function-calling schema, implement it with authentication, and update the system prompt.

### 3. Documentation (update `AGENT.md`)

Update `AGENT.md` to document the `query_api` tool, its authentication, and how the LLM decides between wiki and system tools.

### 4. Tests (5 more tests)

Add 5 regression tests for system agent tools. Example questions:

- `"What framework does the backend use?"` → expects `read_file` in tool_calls.
- `"How many items are in the database?"` → expects `query_api` in tool_calls.

### 5. Deployment

Deploy the updated agent to your VM. Make sure both `.env.agent.secret` (LLM key) and `.env.docker.secret` (backend API key) are configured.

### 6. Benchmark

Run `uv run run_eval.py` — it now includes system questions on top of wiki questions.

## Acceptance criteria

- [ ] `plans/task-3.md` exists with the implementation plan (committed before code).
- [ ] `agent.py` defines `query_api` as a function-calling schema.
- [ ] `query_api` authenticates with `LMS_API_KEY`.
- [ ] The agent answers static system questions correctly (framework, ports, status codes).
- [ ] The agent answers data-dependent questions with plausible values.
- [ ] `AGENT.md` documents the `query_api` tool and system prompt updates.
- [ ] 5 tool-calling regression tests exist and pass.
- [ ] The agent works on the VM via SSH.
- [ ] The benchmark passes all Task 2 and Task 3 questions locally.
- [ ] [Git workflow](../../../wiki/git-workflow.md): issue `[Task] The System Agent`, branch, PR with `Closes #...`, partner approval, merge.
