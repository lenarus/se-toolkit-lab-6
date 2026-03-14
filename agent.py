#!/usr/bin/env python3
import os
import sys
import json

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


def main():
    # Load .env.agent.secret if present in project root
    here = os.path.dirname(os.path.abspath(__file__))
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

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer concisely.",
            },
            {"role": "user", "content": question},
        ],
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=55)
    except requests.exceptions.RequestException as e:
        print(f"LLM request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"LLM returned status {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    try:
        data = resp.json()
    except Exception as e:
        print(f"Failed to parse JSON from LLM response: {e}", file=sys.stderr)
        sys.exit(1)

    # Try to extract assistant content robustly
    answer_text = None
    try:
        choices = data.get("choices", [])
        if choices and isinstance(choices, list):
            first = choices[0]
            # New-style: choices[0].message.content
            msg = first.get("message") if isinstance(first, dict) else None
            if msg and isinstance(msg, dict):
                answer_text = msg.get("content")
            # Fallback: choices[0].text
            if not answer_text:
                answer_text = first.get("text")
    except Exception:
        answer_text = None

    if not answer_text:
        print(
            "LLM response did not contain an assistant answer in choices[0].message.content or choices[0].text",
            file=sys.stderr,
        )
        sys.exit(1)

    answer_text = answer_text.strip()

    output = {"answer": answer_text, "tool_calls": []}

    # Only print one JSON line to stdout
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
