"""Personal Claude Router

Routes each incoming /v1/messages request to the appropriate model tier based on
prompt content. Default is Sonnet. Escalates to Opus for complex work. Fable and
Sonnet are available via %tag overrides that persist for the conversation.

Subscription passthrough: forwards the caller's own Authorization bearer straight
to api.anthropic.com. No API key stored anywhere.
"""
import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

UPSTREAM = os.environ.get("UPSTREAM", "https://api.anthropic.com")

FABLE  = "claude-fable-5"
HAIKU  = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"
OPUS   = "claude-opus-4-8"
OPUS_KEYWORDS  = ("refactor", "debug", "architecture")
BACKGROUND_HINT = "haiku"   # haiku-class requests are internal background calls — leave alone
OAUTH_BETA = "oauth-2025-04-20"

# Prompt-leading tags for manual model selection.
TAG_MODELS = {
  "%s": SONNET, "%o": OPUS, "%f": FABLE, "%a": None,  # %a resumes auto-routing
}

STATE = {"override": None, "last": None, "picked_by": "auto"}

app = FastAPI()


def _split_tag(text: str):
  """If the first word of text is a %tag, return (tag, rest), else (None, text)."""
  head = text.lstrip()
  first, _, rest = head.partition(" ") if " " in head else head.partition("\n")
  if first.lower() in TAG_MODELS:
    return first.lower(), rest.lstrip()
  return None, text


def _consume_tag(body: dict):
  """Strip a leading %tag from the latest user message and return it, or None."""
  for msg in reversed(body.get("messages", [])):
    if msg.get("role") != "user":
      continue
    content = msg.get("content")
    if isinstance(content, str):
      tag, rest = _split_tag(content)
      if tag is not None:
        msg["content"] = rest
      return tag
    elif isinstance(content, list):
      for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
          tag, rest = _split_tag(str(block.get("text", "")))
          if tag is not None:
            block["text"] = rest
          return tag
    return None
  return None


def _latest_user_text(body: dict) -> str:
  """Return only the current turn's user text (not the full history)."""
  for msg in reversed(body.get("messages", [])):
    if msg.get("role") != "user":
      continue
    content = msg.get("content")
    if isinstance(content, str):
      return content
    if isinstance(content, list):
      return "\n".join(
        str(b.get("text", "")) for b in content
        if isinstance(b, dict) and b.get("type") == "text"
      )
    return ""
  return ""


def _pick(text: str) -> str:
  """Auto-route: Opus for complex work, Sonnet for everything else."""
  if any(kw in text.lower() for kw in OPUS_KEYWORDS):
    return OPUS
  return SONNET


def _family(model: str) -> str:
  for name in ("opus", "sonnet", "haiku", "fable"):
    if name in model.lower():
      return name
  return model


def route(body: dict, requested: str) -> tuple[str, bool]:
  """Decide which model to use. Returns (model, is_background)."""
  if requested and BACKGROUND_HINT in requested.lower():
    return requested, True  # internal background call — do not touch

  tag = _consume_tag(body)
  if tag is not None:
    STATE["override"] = TAG_MODELS[tag]

  if STATE["override"]:
    model = STATE["override"]
    STATE["picked_by"] = "locked"
  else:
    model = _pick(_latest_user_text(body))
    STATE["picked_by"] = "auto"

  # If the caller requested the same model family, keep their exact variant
  # (e.g. preserves version pins and long-context model IDs).
  if requested and _family(model) == _family(requested):
    model = requested

  STATE["last"] = model
  return model, False


def _forward_headers(request: Request) -> dict:
  fwd = {
    k: v for k, v in request.headers.items()
    if k.lower() not in ("host", "content-length", "accept-encoding")
  }
  # For subscription auth (Bearer token), ensure the OAuth beta header is present.
  # For API key auth (x-api-key), leave headers as-is.
  using_api_key = any(k.lower() == "x-api-key" for k in fwd)
  if not using_api_key:
    beta_key = next((k for k in fwd if k.lower() == "anthropic-beta"), None)
    betas = fwd.get(beta_key, "") if beta_key else ""
    if "oauth" not in betas:
      fwd[beta_key or "anthropic-beta"] = (betas + "," + OAUTH_BETA).lstrip(",")
  fwd["accept-encoding"] = "identity"
  return fwd


def _strip_long_context_beta(headers: dict):
  """Remove 1M-context beta flags that are only valid for specific model variants."""
  key = next((k for k in headers if k.lower() == "anthropic-beta"), None)
  if not key:
    return
  kept = [t.strip() for t in headers[key].split(",") if t.strip() and "context-1m" not in t]
  if kept:
    headers[key] = ",".join(kept)
  else:
    del headers[key]


@app.get("/health")
async def health():
  return {"status": "ok", "upstream": UPSTREAM}


@app.get("/last-routed")
async def last_routed():
  return JSONResponse({
    "model":     STATE["last"],
    "picked_by": STATE["picked_by"],
    "override":  STATE["override"],
  })


@app.post("/reset")
async def reset():
  """Reset to auto-routing (Sonnet default). Call at session start."""
  STATE["override"] = None
  STATE["last"]     = None
  STATE["picked_by"] = "auto"
  return JSONResponse({"ok": True})


@app.post("/v1/messages")
async def messages(request: Request):
  body = await request.json()
  requested = body.get("model") or ""
  routed, background = route(body, requested)
  body["model"] = routed

  fwd_headers = _forward_headers(request)
  if routed != requested:
    _strip_long_context_beta(fwd_headers)

  client = httpx.AsyncClient(timeout=httpx.Timeout(600.0))
  upstream_resp = await client.send(
    client.build_request("POST", f"{UPSTREAM}/v1/messages", json=body, headers=fwd_headers),
    stream=True,
  )

  out_headers = {
    k: v for k, v in upstream_resp.headers.items()
    if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
  }
  out_headers["x-routed-to"]    = routed
  out_headers["x-routed-by"]    = "auto" if not background else "exempt"

  async def stream():
    try:
      async for chunk in upstream_resp.aiter_raw():
        yield chunk
    finally:
      await upstream_resp.aclose()
      await client.aclose()

  return StreamingResponse(
    stream(), status_code=upstream_resp.status_code,
    headers=out_headers, media_type=upstream_resp.headers.get("content-type"),
  )


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def passthrough(full_path: str, request: Request):
  raw = await request.body()
  fwd_headers = _forward_headers(request)
  client = httpx.AsyncClient(timeout=httpx.Timeout(600.0))
  upstream_resp = await client.send(
    client.build_request(
      request.method, f"{UPSTREAM}/{full_path}",
      content=raw, headers=fwd_headers, params=request.query_params,
    ),
    stream=True,
  )
  out_headers = {
    k: v for k, v in upstream_resp.headers.items()
    if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
  }

  async def stream():
    try:
      async for chunk in upstream_resp.aiter_raw():
        yield chunk
    finally:
      await upstream_resp.aclose()
      await client.aclose()

  return StreamingResponse(
    stream(), status_code=upstream_resp.status_code,
    headers=out_headers, media_type=upstream_resp.headers.get("content-type"),
  )
