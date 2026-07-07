# Changelog

## 1.0.0 — 2026-07-07

Initial release.

- Subscription-only passthrough to Anthropic (no API key)
- Auto-routing: Sonnet default, Opus for complex prompts
- `%s` / `%o` / `%f` / `%a` tags for per-conversation model lock
- `/last-routed` and `/reset` endpoints for client hooks
- systemd service unit for always-on homelab deployment
- Optional end-of-turn model footer hook
- Optional session-reset hook
