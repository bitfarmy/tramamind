#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# TramaMind — chat CLI
# Mostra provenienza (provider/modello), latenza e token dopo
# ogni risposta. Logga tutto in data/requests.jsonl.
#
# Uso:
#   ./scripts/chat.sh                  # modalità interattiva
#   ./scripts/chat.sh "una domanda"    # singolo colpo
#   ./scripts/chat.sh --code "refactor questa funzione"
#   ./scripts/chat.sh --think          # interattiva con deepseek-r1
#   TRAMAMIND_MODEL=qwen3:8b ./scripts/chat.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
DATA_DIR="$ROOT_DIR/data"
LOG_FILE="$DATA_DIR/requests.jsonl"

TRAMAMIND_ENDPOINT="${TRAMAMIND_ENDPOINT:-http://localhost:20128/v1/chat/completions}"
TRAMAMIND_MODEL="${TRAMAMIND_MODEL:-auto}"
TRAMAMIND_TIMEOUT="${TRAMAMIND_TIMEOUT:-120}"
TRAMAMIND_MODE="${TRAMAMIND_MODE:-auto}"
SYSTEM_PROMPT="${SYSTEM_PROMPT:-Sei TramaMind, assistente personale. Rispondi in italiano, in modo denso e concreto.}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# ── Alias per task → modello (override in .env) ─────────────
ALIAS_CODE="${ALIAS_CODE:-qwen2.5-coder:7b}"
ALIAS_THINK="${ALIAS_THINK:-deepseek-r1:8b}"
ALIAS_FAST="${ALIAS_FAST:-gemma3:4b}"
ALIAS_WRITE="${ALIAS_WRITE:-qwen3:8b}"

alias_model() {
  case "$1" in
    code)  printf '%s' "$ALIAS_CODE" ;;
    think) printf '%s' "$ALIAS_THINK" ;;
    fast)  printf '%s' "$ALIAS_FAST" ;;
    write) printf '%s' "$ALIAS_WRITE" ;;
    *) return 1 ;;
  esac
}

mkdir -p "$DATA_DIR"

if [[ -t 1 ]]; then
  C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_CYAN=$'\033[36m'
  C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_DIM=""; C_BOLD=""; C_CYAN=""; C_GREEN=""; C_RED=""; C_RESET=""
fi

err() { printf '%s✗ %s%s\n' "$C_RED" "$1" "$C_RESET" >&2; }

print_aliases() {
  printf '%salias per task:%s\n' "$C_BOLD" "$C_RESET"
  local a m mark
  for a in code think fast write; do
    m="$(alias_model "$a")"
    mark=" "
    [[ "$m" == "$TRAMAMIND_MODEL" ]] && mark="*"
    printf '  %s %-7s → %s\n' "$mark" "--$a" "$m"
  done
  printf '%s(* = attivo · /use NOME per cambiare)%s\n' "$C_DIM" "$C_RESET"
}

for cmd in curl python3; do
  command -v "$cmd" >/dev/null 2>&1 || { err "manca '$cmd' — vedi docs/setup.md"; exit 1; }
done

HISTORY_FILE="$(mktemp /tmp/tramamind-history.XXXXXX.json)"
HEADERS_FILE="$(mktemp /tmp/tramamind-headers.XXXXXX)"
META_FILE="$(mktemp /tmp/tramamind-meta.XXXXXX)"
BODY_FILE="$(mktemp /tmp/tramamind-body.XXXXXX.json)"
trap 'rm -f "$HISTORY_FILE" "$HEADERS_FILE" "$META_FILE" "$BODY_FILE"' EXIT
echo "[]" > "$HISTORY_FILE"

# ── Invia un messaggio e stampa risposta + provenienza ───────
send_message() {
  local user_msg="$1"

  python3 - "$HISTORY_FILE" "$user_msg" <<'PY'
import json, sys
path, msg = sys.argv[1], sys.argv[2]
hist = json.load(open(path))
hist.append({"role": "user", "content": msg})
json.dump(hist, open(path, "w"))
PY

  local payload
  payload="$(python3 - "$HISTORY_FILE" "$TRAMAMIND_MODEL" "$SYSTEM_PROMPT" <<'PY'
import json, sys
hist = json.load(open(sys.argv[1]))
model, sysp = sys.argv[2], sys.argv[3]
msgs = ([{"role": "system", "content": sysp}] if sysp else []) + hist
print(json.dumps({"model": model, "messages": msgs, "stream": False}))
PY
)"

  local raw http_code time_total
  local -a curl_auth=()
  if [[ -n "${OMNIROUTE_API_KEY:-}" ]]; then
    curl_auth=(-H "Authorization: Bearer $OMNIROUTE_API_KEY")
  fi
  if ! raw="$(curl -sS --max-time "$TRAMAMIND_TIMEOUT" -D "$HEADERS_FILE" \
      -w '\n__HTTP_CODE__:%{http_code}\n__TIME__:%{time_total}' \
      -H 'Content-Type: application/json' \
      -H "X-TramaMind-Mode: $TRAMAMIND_MODE" \
      "${curl_auth[@]}" \
      -d "$payload" \
      "$TRAMAMIND_ENDPOINT")"; then
    err "router irraggiungibile su $TRAMAMIND_ENDPOINT — ./scripts/start-all.sh"
    return 1
  fi

  http_code="$(printf '%s' "$raw" | sed -n 's/^__HTTP_CODE__://p')"
  time_total="$(printf '%s' "$raw" | sed -n 's/^__TIME__://p')"
  local body
  body="$(printf '%s' "$raw" | sed '/^__HTTP_CODE__:/d;/^__TIME__:/d')"

  if [[ "$http_code" != "200" ]]; then
    err "HTTP $http_code dal router:"
    printf '%s\n' "$body" | head -c 500 >&2; printf '\n' >&2
    # rollback del messaggio utente dalla history
    python3 - "$HISTORY_FILE" <<'PY'
import json, sys
path = sys.argv[1]
hist = json.load(open(path))
if hist: hist.pop()
json.dump(hist, open(path, "w"))
PY
    return 1
  fi

  # Estrae risposta e metadati; scrive meta come KEY=VALUE sanitizzati
  # (il body passa via file: lo stdin di python è occupato dallo script)
  printf '%s' "$body" > "$BODY_FILE"
  local answer
  answer="$(python3 - "$META_FILE" "$HEADERS_FILE" "$BODY_FILE" <<'PY'
import json, re, sys

meta_path, headers_path, body_path = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(body_path, encoding="utf-8").read()

data = json.loads(raw)
answer = data["choices"][0]["message"].get("content") or ""
usage = data.get("usage") or {}

# provenienza: campi body comuni, poi header, poi il campo model
provider = (data.get("provider") or data.get("x_provider")
            or data.get("served_by") or "")
cached = bool(data.get("cached") or data.get("cache_hit"))

try:
    headers = open(headers_path, encoding="utf-8", errors="replace").read().lower()
except OSError:
    headers = ""
if not provider:
    for h in ("x-omniroute-provider:", "x-tramamind-provider:", "x-provider:",
              "x-served-by:"):
        m = re.search(r"^" + re.escape(h) + r"\s*(.+)$", headers, re.M)
        if m:
            provider = m.group(1).strip()
            break
if not cached and re.search(r"^x-cache:\s*hit", headers, re.M):
    cached = True

model = str(data.get("model") or "?")
if not provider:
    # OmniRoute spesso espone "provider/modello" nel campo model
    provider = model.split("/", 1)[0] if "/" in model else "auto"

def clean(v):
    return re.sub(r"[^A-Za-z0-9._/:\-]", "_", str(v))[:80] or "?"

with open(meta_path, "w") as f:
    f.write("P_PROVIDER=%s\n" % clean(provider))
    f.write("P_MODEL=%s\n" % clean(model))
    f.write("P_PT=%d\n" % int(usage.get("prompt_tokens") or 0))
    f.write("P_CT=%d\n" % int(usage.get("completion_tokens") or 0))
    f.write("P_CACHED=%s\n" % ("true" if cached else "false"))

print(answer)
PY
)"

  # shellcheck disable=SC1090
  source "$META_FILE"
  local latency_ms
  latency_ms="$(awk "BEGIN{printf \"%d\", ${time_total:-0}*1000}")"

  # aggiorna history con la risposta
  python3 - "$HISTORY_FILE" "$answer" <<'PY'
import json, sys
path, ans = sys.argv[1], sys.argv[2]
hist = json.load(open(path))
hist.append({"role": "assistant", "content": ans})
json.dump(hist, open(path, "w"))
PY

  # log JSONL per stats.sh
  python3 - "$LOG_FILE" "$P_PROVIDER" "$P_MODEL" "$latency_ms" "$P_PT" "$P_CT" "$P_CACHED" "$TRAMAMIND_MODE" <<'PY'
import json, sys, time
path, prov, model, lat, pt, ct, cached, mode = sys.argv[1:9]
row = {"ts": int(time.time()), "provider": prov, "model": model,
       "latency_ms": int(lat), "prompt_tokens": int(pt),
       "completion_tokens": int(ct),
       "cached": cached == "true", "mode": mode}
with open(path, "a") as f:
    f.write(json.dumps(row) + "\n")
PY

  # output
  printf '%s\n' "$answer"
  local cache_tag=""
  [[ "$P_CACHED" == "true" ]] && cache_tag=" · cache:hit"
  printf '%s⚡ provider=%s%s%s · modello=%s · %s%sms%s · %s token (in %s / out %s)%s%s\n\n' \
    "$C_DIM" "$C_GREEN" "$P_PROVIDER" "$C_DIM" "$P_MODEL" \
    "$C_BOLD" "$latency_ms" "$C_DIM" \
    "$((P_PT + P_CT))" "$P_PT" "$P_CT" "$cache_tag" "$C_RESET"
}

# ── Alias da riga di comando: chat.sh --code "..." ───────────
if [[ $# -gt 0 && "$1" == --* ]]; then
  flag="${1#--}"
  if [[ "$flag" == "help" ]]; then
    printf 'Uso: %s [--code|--think|--fast|--write] [messaggio]\n' "$0"
    print_aliases
    exit 0
  fi
  if model="$(alias_model "$flag")"; then
    TRAMAMIND_MODEL="$model"
    shift
  else
    err "alias '--$flag' sconosciuto — usa --help per la lista"
    exit 1
  fi
fi

# ── Singolo colpo o REPL ─────────────────────────────────────
if [[ $# -gt 0 ]]; then
  send_message "$*"
  exit 0
fi

printf '%s%sTramaMind chat%s · modello %s%s%s\n' \
  "$C_BOLD" "$C_CYAN" "$C_RESET" "$C_BOLD" "$TRAMAMIND_MODEL" "$C_RESET"
printf '%sendpoint %s%s\n' "$C_DIM" "$TRAMAMIND_ENDPOINT" "$C_RESET"
printf '%s/exit esce · /model NOME cambia modello · /use NOME cambia alias · /alias mostra gli alias · /clear azzera il contesto%s\n\n' "$C_DIM" "$C_RESET"

while true; do
  printf '%s›%s ' "$C_CYAN" "$C_RESET"
  IFS= read -r line || { printf '\n'; break; }
  case "$line" in
    /exit|/quit) break ;;
    /clear) echo "[]" > "$HISTORY_FILE"; printf '%scontesto azzerato%s\n' "$C_DIM" "$C_RESET" ;;
    /model\ *)
      TRAMAMIND_MODEL="${line#/model }"
      printf '%smodello → %s%s\n' "$C_DIM" "$TRAMAMIND_MODEL" "$C_RESET" ;;
    /alias) print_aliases ;;
    /use\ *)
      use_arg="${line#/use }"
      if use_model="$(alias_model "$use_arg")"; then
        TRAMAMIND_MODEL="$use_model"
        printf '%salias %s attivo → modello %s%s\n' "$C_DIM" "$use_arg" "$TRAMAMIND_MODEL" "$C_RESET"
      else
        err "alias '$use_arg' sconosciuto — prova /alias"
      fi ;;
    "") continue ;;
    *) send_message "$line" || true ;;
  esac
done
