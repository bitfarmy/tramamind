#!/bin/bash
# TramaMind — Benchmark minimo per misurare routing, compressione e cache
# Uso: ./benchmarks/benchmark.sh
#
# Invia un set fisso di prompt al router (due giri: il secondo misura la cache)
# e registra per ogni richiesta: provider usato, latenza, token in/out.
# Risultati in data/benchmark-YYYYmmdd-HHMMSS.csv
#
# Serve per la fase 2 della roadmap: niente stime, solo misure sui propri carichi.

set -u

ENDPOINT="${TRAMAMIND_ENDPOINT:-http://localhost:20128/v1/chat/completions}"
MODEL="${TRAMAMIND_MODEL:-auto}"
TIMEOUT="${TRAMAMIND_TIMEOUT:-120}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/benchmark-$(date +%Y%m%d-%H%M%S).csv"

command -v jq >/dev/null 2>&1 || { echo "❌ jq mancante: sudo apt install jq"; exit 1; }
curl -s --max-time 3 "${ENDPOINT%/chat/completions}/models" >/dev/null 2>&1 || {
  echo "❌ Router non raggiungibile su $ENDPOINT. Serve OmniRoute acceso (tramamind up)."; exit 1;
}

mkdir -p "$ROOT/data"

# Prompt fissi e rappresentativi: modificali per avvicinarli ai tuoi carichi reali
PROMPT_FILE="$ROOT/benchmarks/prompts.txt"
[ -f "$PROMPT_FILE" ] || { echo "❌ File prompt mancante: $PROMPT_FILE"; exit 1; }

echo "giro,prompt,provider,latenza_ms,token_input,token_output" > "$OUT"

giro=0
for giro in 1 2; do
  echo "=== Giro $giro $( [ "$giro" = 2 ] && echo '(misura la cache semantica)' ) ==="
  n=0
  while IFS= read -r prompt; do
    [ -z "$prompt" ] && continue
    n=$((n+1))
    payload=$(jq -n --arg m "$MODEL" --arg q "$prompt" \
      '{model: $m, messages: [{role: "user", content: $q}]}')

    start=$(date +%s%3N)
    response=$(curl -s --max-time "$TIMEOUT" "$ENDPOINT" \
      -H "Content-Type: application/json" -d "$payload")
    end=$(date +%s%3N)
    lat=$((end - start))

    provider=$(echo "$response" | jq -r '.provider // .model // "?"')
    tin=$(echo "$response" | jq -r '.usage.prompt_tokens // "?"')
    tout=$(echo "$response" | jq -r '.usage.completion_tokens // "?"')

    echo "$giro,\"$prompt\",$provider,$lat,$tin,$tout" >> "$OUT"
    printf "  [%d] %-40s provider=%s %dms in=%s out=%s\n" "$n" "${prompt:0:40}" "$provider" "$lat" "$tin" "$tout"
  done < "$PROMPT_FILE"
done

echo ""
echo "✅ Risultati salvati in: $OUT"
echo ""
echo "Come leggere i dati:"
echo "  - Giro 2 con token_input ≈ 0 → cache hit (risparmio 100% su quella richiesta)"
echo "  - Confronta token_input con/senza compressione attiva nella dashboard OmniRoute"
echo "  - La colonna provider mostra come il router distribuisce il carico"
