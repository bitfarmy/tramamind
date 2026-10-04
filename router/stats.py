"""Log delle richieste: metadati, mai il testo."""
from __future__ import annotations

import json

from router.paths import log_path


def append_log(row: dict) -> None:
    with log_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_log() -> list[dict]:
    path = log_path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarize(rows: list[dict] | None = None) -> dict:
    rows = read_log() if rows is None else rows
    if not rows:
        return {"n": 0, "escalated": 0, "avg_sent": 0, "avg_raw": 0, "saved_pct": 0}
    sent = [int(row.get("packet_tokens_est") or 0) for row in rows]
    raw = [int(row.get("raw_tokens_est") or 0) for row in rows]
    raw_sum = sum(raw)
    sent_sum = sum(sent)
    saved = 0 if raw_sum <= 0 else round(100 * (raw_sum - sent_sum) / raw_sum)
    return {
        "n": len(rows),
        "escalated": sum(1 for row in rows if row.get("escalated")),
        "avg_sent": round(sent_sum / len(rows)),
        "avg_raw": round(raw_sum / len(rows)),
        "saved_pct": max(0, saved),
    }


def render_summary(stats: dict) -> str:
    if stats["n"] == 0:
        return "Nessuna richiesta registrata."
    return (
        f"{stats['n']} richieste · escalation {stats['escalated']} · "
        f"pacchetto medio ~{stats['avg_sent']} · storia intera media ~{stats['avg_raw']} · "
        f"−{stats['saved_pct']}% stimato"
    )
