# Pass the Benchmark

<h4>Time</h4>

~120 min

<h4>Purpose</h4>

Iterate on your agent until it passes the full evaluation benchmark, including hidden questions that require chaining tools to diagnose bugs from application logs.

<h4>Context</h4>

Your agent can read docs and query the API. Now it needs to handle harder questions: multi-step challenges where the agent must find an error in the application logs, trace it to the source file, identify the bug, and suggest a fix. These require chaining tools (query logs → read source → reason about fix). The autochecker tests additional hidden questions beyond what `run_eval.py` shows — you need a genuinely working agent, not hard-coded answers.

<h4>Table of contents</h4>

- [1. Steps](#1-steps)
  - [1.1. Follow the `Git workflow`](#11-follow-the-git-workflow)
  - [1.2. Create a `Lab Task` issue](#12-create-a-lab-task-issue)
  - [1.3. Run the benchmark and write a plan](#13-run-the-benchmark-and-write-a-plan)
  - [1.4. Iterate on the agent](#14-iterate-on-the-agent)
  - [1.5. Update documentation](#15-update-documentation)
  - [1.6. Update tests](#16-update-tests)
  - [1.7. Deploy to your VM](#17-deploy-to-your-vm)
  - [1.8. Finish the task](#18-finish-the-task)
  - [1.9. Check the task using the autochecker](#19-check-the-task-using-the-autochecker)
- [2. Acceptance criteria](#2-acceptance-criteria)

## 1. Steps

### 1.1. Follow the `Git workflow`

Follow the [`Git workflow`](../../../wiki/git-workflow.md) to complete this task.

### 1.2. Create a `Lab Task` issue

Title: `[Task] Pass the Benchmark`

### 1.3. Run the benchmark and write a plan

1. Run the full benchmark:

   ```terminal
   python run_eval.py
   ```

2. Create `plans/task-3.md`. Document:

   - Your current score (e.g., "18/26 passed").
   - The first few failures and your diagnosis of each.
   - Your strategy for improving the agent.

Commit:

```text
docs: add benchmark iteration plan
```

### 1.4. Iterate on the agent

Run the benchmark, examine failures, fix your agent, and repeat.

```
run eval → see failure → diagnose → fix agent → re-run → next failure → ...
```

When a question fails, the benchmark shows a feedback hint:

```
  ✗ [22/26] Compare how the ETL pipeline handles failures vs the API endpoints.
    feedback: Read both the ETL code and the API router code, then compare their error handling.
```

Use this debugging workflow:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Wrong factual answer | System prompt missing this topic | Add the topic to your system prompt |
| Agent doesn't use a tool when it should | Tool description too vague for the LLM | Improve the tool's description in the schema |
| Tool called but returns an error | Bug in tool implementation | Fix the tool code, test it in isolation |
| Tool called with wrong arguments | LLM misunderstands the schema | Clarify parameter descriptions |
| Agent times out | Too many tool calls or slow LLM | Reduce max iterations, try a faster model |
| Answer is close but doesn't match | Phrasing doesn't contain expected keyword | Adjust system prompt to be more precise |

> [!NOTE]
> The autochecker bot tests your agent with additional hidden questions not present in `run_eval.py`. These include multi-step challenges that require chaining tools: finding errors in application logs, tracing them to source files, and suggesting fixes. A well-built agent with good tools and prompts will handle these naturally — you don't need to know the exact questions.

Commit as you go. Example:

```text
fix: improve system prompt for Docker questions
fix: handle empty file in read_file tool
feat: add retry logic for LLM API rate limits
```

### 1.5. Update documentation

Update `AGENT.md` with:

- **Final architecture**: any changes made during iteration.
- **Lessons learned**: what failed and why, what you changed.
- **Eval score**: your final `run_eval.py` result.

Commit:

```text
docs: update agent documentation with benchmark results
```

### 1.6. Update tests

Update your regression tests to cover any new edge cases you discovered during iteration.

Commit:

```text
test: update regression tests with benchmark edge cases
```

### 1.7. Deploy to your VM

Deploy the final agent to your VM. The autochecker bot will run the full benchmark including hidden questions.

1. Push your branch and pull on the VM.
2. Verify the agent passes locally on the VM:

   ```terminal
   cd ~/se-toolkit-lab-6
   python agent.py "What framework does the backend use?"
   ```

You need at least **75%** of all questions (shared + hidden) to pass.

### 1.8. Finish the task

1. [Create a PR](../../../wiki/git-workflow.md#create-a-pr) with your changes.
2. [Get a PR review](../../../wiki/git-workflow.md#get-a-pr-review) and complete the subsequent steps in the `Git workflow`.

### 1.9. Check the task using the autochecker

[Check the task using the autochecker `Telegram` bot](../../../wiki/autochecker.md#check-the-task-using-the-autochecker-bot).

---

## 2. Acceptance criteria

- [ ] Issue has the correct title.
- [ ] `plans/task-3.md` exists with the initial diagnosis and strategy.
- [ ] `run_eval.py` passes all local questions.
- [ ] The autochecker bot benchmark passes at least 75%.
- [ ] `AGENT.md` documents the final architecture and lessons learned (at least 200 words).
- [ ] Regression tests are updated.
- [ ] The agent works on the VM via `SSH`.
- [ ] PR is approved and merged.
- [ ] Issue is closed by the PR.
