# Ollama LLM Integration for Task Detection

## Access from WSL2

Ollama runs on the Windows host. From WSL2, access it via the gateway IP:

```bash
# Find the gateway IP (CHANGES at every WSL2 reboot)
GW=$(ip route show default | awk '{print $3}')
curl -s http://$GW:11434/api/tags
```

**⚠️ Do NOT hard-code the gateway IP** — it changes on every PC/WSL restart.
Current best practice: detect via `ip route show default` (see `process_emails.py`).

## Available Models

| Model | Size | Thinking? | JSON Output | Speed |
|---|---|---|---|---|
| `qwen3-openclaw:latest` | 9.7B | Yes (always on) | Reliable with num_predict=4096 | ~60s |
| `qwen3.5:9b` | 9.7B | Yes (always on) | Needs num_predict >= 4096 | ~60s |
| `hermes-extreme:latest` | 9.7B | Yes (always on) | **Needs num_predict >= 8192** | ~70-90s |
| `llama3.1:latest` | 8B | No | Reliable | ~20s |
| `qwen2.5-coder:7b` | 7.6B | No | Yes | ~26s |
| `gemma3:12b` | 12.2B | No | Yes | ~30s |

## Model Selection for Task Detection

**Use `qwen3-openclaw:latest`** — custom Qwen3.5:9B with expanded context window. Best balance of quality and context handling.

### Qwen3 Thinking Model Gotcha

Qwen3 models with thinking enabled **always** think — `think: False` is NOT supported. They consume ~10K tokens for thinking before producing a response.

**Critical**: Must set `num_predict` high (4096 for qwen3, **8192 for hermes-extreme**). With lower values the `response` field is empty and `thinking` is truncated. Long email prompts with a 1500-char body need even more headroom — `8192` is the safe value for `hermes-extreme`. Expect ~40-90s per email.

> **2026-08-20 lesson**: even `num_predict: 4096` was NOT enough for `hermes-extreme` on real email prompts (eval_count hit 4096, response came back empty). Bumped to 8192 → works. Set generous HTTP timeouts (>=300s).

### himalaya `message read` Returns Raw Text

`himalaya message read <id> -o json` returns **raw email text**, NOT structured JSON. Must parse headers manually (From, Subject, body after first blank line). Only `himalaya envelope list -o json` returns proper JSON.
