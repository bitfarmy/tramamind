#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# TramaMind — statistiche consumi
# Legge data/requests.jsonl e mostra:
#   · richieste e token per provider
#   · cache hit rate
#   · stima del risparmio vs prezzo di riferimento cloud
#
# Uso:
#   ./scripts/stats.sh
#   REF_PRICE_PER_MTOK=2.00 ./scripts/stats.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$ROOT_DIR/data/requests.jsonl"
REF_PRICE_PER_MTOK="${REF_PRICE_PER_MTOK:-2.00}"

if [[ ! -s "$LOG_FILE" ]]; then
  echo "Nessun log in $LOG_FILE — fai qualche richiesta con ./scripts/chat.sh"
  exit 0
fi

python3 - "$LOG_FILE" "$REF_PRICE_PER_MTOK" <<'PY'
import collections
import datetime
import json
import sys

path, price = sys.argv[1], float(sys.argv[2])

rows = []
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

if not rows:
    print("Log vuoto.")
    sys.exit(0)

by_prov = collections.defaultdict(lambda: {"n": 0, "tin": 0, "tout": 0, "lat": []})
hits = 0
cached_tokens = 0
local_tokens = 0

for r in rows:
    prov = r.get("provider") or "sconosciuto"
    d = by_prov[prov]
    d["n"] += 1
    pt = r.get("prompt_tokens") or 0
    ct = r.get("completion_tokens") or 0
    d["tin"] += pt
    d["tout"] += ct
    if r.get("latency_ms"):
        d["lat"].append(r["latency_ms"])
    if r.get("cached"):
        hits += 1
        cached_tokens += pt + ct
    if prov.startswith(("local", "ollama")):
        local_tokens += pt + ct

total = len(rows)
tot_in = sum(d["tin"] for d in by_prov.values())
tot_out = sum(d["tout"] for d in by_prov.values())
hit_rate = (hits / total * 100) if total else 0.0

first = datetime.datetime.fromtimestamp(min(r.get("ts", 0) for r in rows))
last = datetime.datetime.fromtimestamp(max(r.get("ts", 0) for r in rows))

def migliaia(n):
    return f"{n:,}".replace(",", ".")

print()
print("  TramaMind — statistiche")
print("  " + "─" * 56)
print(f"  Periodo: {first:%d %b %Y %H:%M} → {last:%d %b %Y %H:%M}")
print(f"  Richieste totali: {total}   Token: {migliaia(tot_in + tot_out)} "
      f"(in {migliaia(tot_in)} / out {migliaia(tot_out)})")
print()
print(f"  {'PROVIDER':<22}{'REQ':>5}{'TOKEN IN':>12}{'TOKEN OUT':>12}{'LAT MEDIA':>11}")
print("  " + "─" * 56)
for prov, d in sorted(by_prov.items(), key=lambda kv: -kv[1]["n"]):
    avg = int(sum(d["lat"]) / len(d["lat"])) if d["lat"] else 0
    print(f"  {prov:<22}{d['n']:>5}{migliaia(d['tin']):>12}{migliaia(d['tout']):>12}"
          f"{str(avg) + 'ms':>11}")
print("  " + "─" * 56)
print()
print(f"  Cache: {hits}/{total} hit ({hit_rate:.1f}%)"
      f" — {migliaia(cached_tokens)} token risparmiati")

saved_tokens = cached_tokens + local_tokens
saved_usd = saved_tokens * price / 1_000_000
print(f"  Stima risparmio (cache + locale vs ${price:.2f}/Mtok): "
      f"{migliaia(saved_tokens)} token ≈ ${saved_usd:.4f}")
print()
PY
