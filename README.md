# personal claude router

![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen)
![License](https://img.shields.io/badge/License-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
[![GitHub issues](https://img.shields.io/github/issues/pdubbbbbs/personal-claude-router)](https://github.com/pdubbbbbs/personal-claude-router/issues)

A self-hosted proxy that automatically picks the right Claude model for every prompt. Runs on any Linux homelab node. Uses your Claude subscription — no API key required.

## Features

- **Automatic model selection** — picks Sonnet or Opus based on prompt content, you never have to choose
- **Per-conversation model lock** — tag a message with `%o`, `%s`, or `%f` to lock the model for the rest of the conversation
- **Flexible auth** — works with a Claude subscription (no API key) or a standard Anthropic API key
- **End-of-turn feedback** — optional hook shows which model answered and how to switch
- **Session reset** — optional hook resets to Sonnet default at the start of each new session
- **Always-on** — runs as a systemd service, restarts automatically on failure or reboot

## How it works

Every prompt routes through this proxy. It reads the content and picks:

| Condition | Model |
|---|---|
| Contains `refactor`, `debug`, or `architecture` | **Opus** (most capable) |
| Everything else | **Sonnet** (default) |

Internal background calls made by the client are left untouched.

## Model switching

Start a message with a tag to lock the model for the rest of that conversation:

| Tag | Model |
|---|---|
| `%s` | Sonnet 4.6 |
| `%o` | Opus 4.8 |
| `%f` | Fable 5 |
| `%a` | Resume auto-routing |

## Prerequisites

**Required:**
- Linux homelab node (x86_64 or arm64)
- Python 3.10+
- Claude Pro or Max subscription **or** an Anthropic API key
- Claude Code installed on your client machine

**Optional:**
- systemd (for always-on service)

## Installation

**1. Clone the repo on your homelab node**

```bash
git clone https://github.com/pdubbbbbs/personal-claude-router.git
cd personal-claude-router
```

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**3. Install as a systemd service**

```bash
sed -i "s/YOUR_USER/$USER/g" systemd/personal-claude-router.service
sudo cp systemd/personal-claude-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now personal-claude-router
```

**4. Verify it is running**

```bash
curl http://localhost:4000/health
# {"status":"ok","upstream":"https://api.anthropic.com"}
```

**5. Point your Claude client at the router**

Add to `~/.claude/settings.json` on your client machine:

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://<your-node-ip>:4000"
}
```

**With a Claude subscription (no API key):** your subscription token passes through automatically — nothing else needed.

**With an Anthropic API key:** also set `ANTHROPIC_API_KEY` in the same `env` block and the router will forward it.

## Optional: end-of-turn model footer

After each answer, display which model was used and how to switch. Add to `~/.claude/settings.json`:

```json
"Stop": [{
  "hooks": [{
    "type": "command",
    "command": "bash ~/.claude/hooks/model-footer.sh",
    "timeout": 6
  }]
}]
```

Copy `hooks/model-footer.sh` from this repo to `~/.claude/hooks/model-footer.sh`.

Result:

```
🧭 Sonnet 4.6 (auto-picked). Start next message with %s / %o / %f to switch — %a for auto.
```

## Optional: reset to Sonnet at session start

Add to the `SessionStart` hooks in `~/.claude/settings.json`:

```json
"SessionStart": [{
  "hooks": [{
    "type": "command",
    "command": "curl -s -m 3 -X POST http://<your-node-ip>:4000/reset",
    "timeout": 6
  }]
}]
```

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/last-routed` | GET | Model used for the last main prompt |
| `/reset` | POST | Reset to auto-routing (Sonnet default) |
| `/v1/messages` | POST | Anthropic Messages API — routed |
| `/*` | ANY | Passthrough to Anthropic unchanged |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — Philip S. Wright
