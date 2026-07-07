#!/usr/bin/env bash
# Add to ~/.claude/hooks/model-footer.sh
# Shows which model answered after each turn and how to switch.
set -uo pipefail
ROUTER_URL="${ROUTER_URL:-http://localhost:4000}"
resp="$(curl -s -m 3 "$ROUTER_URL/last-routed")" || exit 0
[ -z "$resp" ] && exit 0
MODEL=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('model',''))" <<< "$resp" 2>/dev/null)
PICKED=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('picked_by','auto'))" <<< "$resp" 2>/dev/null)
[ -z "${MODEL:-}" ] && exit 0
case "$MODEL" in *fable*) P="Fable 5";; *haiku*) P="Haiku 4.5";; *sonnet*) P="Sonnet 4.6";; *opus*) P="Opus 4.8";; *) P="$MODEL";; esac
[ "$PICKED" = "locked" ] && S="locked" || S="auto-picked"
python3 -c "import json,sys; print(json.dumps({'systemMessage': sys.argv[1]}))" \
  "🧭 ${P} (${S}). Start next message with %s / %o / %f to switch — %a for auto."
