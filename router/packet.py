"""Cosa entra nel prompt. Il tetto si applica qui, non con una compressione cieca."""
from __future__ import annotations

import math
import re

CODE_RE = re.compile(
    r"```|traceback|stack trace|\b(refactor|funzione|function|bug|python|javascript|"
    r"typescript|compil|sql|regex|stacktrace)\b",
    re.IGNORECASE,
)
THINK_RE = re.compile(
    r"\b(passo passo|ragiona|dimostra|dimostrazione|analizza a fondo|step by step)\b",
    re.IGNORECASE,
)
RETRY_RE = re.compile(
    r"\b(rifallo meglio|rifai meglio|riprova meglio|riprova|non basta|"
    r"più preciso|piu preciso|risposta sbagliata)\b",
    re.IGNORECASE,
)
WEAK_RE = re.compile(
    r"(mi dispiace,\s*ma non|come modello|come intelligenza artificiale|"
    r"non sono in grado|non posso aiut|as an ai language model|"
    r"^non lo so[.!]?\s*$|^i cannot\b|^i'm sorry\b)",
    re.IGNORECASE | re.MULTILINE,
)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

SUMMARY_CAP_TOKENS = 450
MESSAGE_OVERHEAD = 4
EXCERPT_CHARS = 1500
EXCERPT_LIMIT = 4

_TB_RE = re.compile(
    r"Traceback \(most recent call last\):\n(?:[ \t].*\n|\n)*?"
    r"[A-Za-z_][\w.]*(?:Error|Exception|Interrupt|Exit)(?::[^\n]*)?",
    re.MULTILINE,
)


def estimate_tokens(text: str) -> int:
    """Stima stabile, usata sia per il pacchetto sia per la storia intera."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 3.5))


def classify(text: str) -> str:
    if CODE_RE.search(text):
        return "code"
    if THINK_RE.search(text):
        return "think"
    return "general"


def wants_retry(text: str) -> bool:
    return RETRY_RE.search(text) is not None


def is_weak(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) > 400:
        return False
    return WEAK_RE.search(stripped) is not None


def omni_model(model: str) -> str:
    prefixes = (
        "groq/", "gemini/", "google/", "nvidia/", "openrouter/",
        "cerebras/", "moonshot/", "kimi/", "ollama/",
    )
    if model.startswith(prefixes):
        return model
    return "groq/" + model


def groq_model(model: str) -> str:
    if model.startswith("groq/"):
        return model[len("groq/"):]
    return model


def _text_tokens(text: str) -> int:
    return estimate_tokens(text) + MESSAGE_OVERHEAD


def conversation_tokens(system: str, messages: list[dict]) -> int:
    total = _text_tokens(system)
    for message in messages:
        total += _text_tokens(message.get("content") or "")
    return total


def system_with_summary(system: str, summary: str) -> str:
    if not summary.strip():
        return system
    return system + "\n\nContesto delle puntate precedenti:\n" + summary.strip()


def packet_tokens(system: str, summary: str, tail: list[dict]) -> int:
    return conversation_tokens(system_with_summary(system, summary), tail)


def split_history(
    history: list[dict], budget: int, verbatim: int, system: str
) -> tuple[list[dict], list[dict]]:
    """Tiene gli ultimi turni interi. Il resto andrà nel riassunto."""
    if not history:
        return [], []
    tail_n = min(max(verbatim, 1), len(history))
    while tail_n > 1:
        tail = history[-tail_n:]
        reserve = SUMMARY_CAP_TOKENS if tail_n < len(history) else 0
        if conversation_tokens(system, tail) + reserve <= budget:
            break
        tail_n -= 1
    return history[:-tail_n], history[-tail_n:]


def fit_summary(
    system: str,
    prose: str,
    fences: list[str],
    tail: list[dict],
    budget: int,
) -> str:
    prose = prose.strip()
    while prose and packet_tokens(system, prose, tail) > budget and len(prose) > 40:
        prose = prose[: max(40, int(len(prose) * 0.75))].rstrip()
    if prose and packet_tokens(system, prose, tail) > budget:
        prose = ""
    ordered = [piece for piece in fences if piece][:EXCERPT_LIMIT]
    # Il più recente entra per primo: un diff vecchio non occupa il posto di quello appena successo.
    selected: list[str] = []
    for excerpt in reversed(ordered):
        trial = _with_excerpts(prose, selected + [excerpt], ordered)
        if packet_tokens(system, trial, tail) <= budget:
            selected.append(excerpt)
    return _with_excerpts(prose, selected, ordered)


def _with_excerpts(prose: str, selected: list[str], ordered: list[str]) -> str:
    parts = [prose] if prose else []
    for piece in ordered:
        if piece in selected:
            parts.append(piece)
    return "\n\n".join(parts).strip()


def compose(system: str, summary: str, tail: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": system_with_summary(system, summary)}]
    for message in tail:
        messages.append({"role": message["role"], "content": message.get("content") or ""})
    return messages


def build_packet(
    *,
    history: list[dict],
    system: str,
    summary: str,
    budget: int,
    verbatim: int,
    fences: list[str] | None = None,
) -> dict:
    """Ritorna messages, conteggi e quanto della storia è stato riassunto."""
    raw_messages = [{"role": "system", "content": system}, *history]
    raw_tokens = conversation_tokens(system, history)
    head, tail = split_history(history, budget, verbatim, system)
    if not head:
        messages = compose(system, "", tail)
        return {
            "messages": messages,
            "raw_tokens": raw_tokens,
            "sent_tokens": conversation_tokens(system, tail),
            "summarized": False,
            "head_len": 0,
            "raw_messages": raw_messages,
        }
    fitted = fit_summary(system, summary, fences or [], tail, budget)
    messages = compose(system, fitted, tail)
    return {
        "messages": messages,
        "raw_tokens": raw_tokens,
        "sent_tokens": packet_tokens(system, fitted, tail),
        "summarized": True,
        "head_len": len(head),
        "summary": fitted,
        "raw_messages": raw_messages,
    }


def _content_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part.get("text") or ""))
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _diff_line(line: str) -> bool:
    return line.startswith((
        "diff --git ", "index ", "--- ", "+++ ", "@@",
        "new file mode", "deleted file mode", "old mode", "new mode",
        "similarity index", "rename from", "rename to", "Binary files",
        "+", "-", "\\",
    )) or (line.startswith(" ") and line.strip() != "")


def diff_blocks(text: str) -> list[str]:
    """Unified diff. Una riga che inizia con «- » non basta: serve l'intestazione."""
    lines = text.splitlines()
    blocks = []
    index = 0
    while index < len(lines):
        starts = lines[index].startswith("diff --git ") or (
            lines[index].startswith("--- ")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("+++ ")
        )
        if not starts:
            index += 1
            continue
        end = index + 1
        while end < len(lines) and _diff_line(lines[end]):
            end += 1
        block = "\n".join(lines[index:end]).strip()
        if block and ("@@" in block or block.startswith("diff --git ")):
            blocks.append(block)
        index = end
    return blocks


def traceback_blocks(text: str) -> list[str]:
    return [match.group(0).strip() for match in _TB_RE.finditer(text)]


def plain_prose(text: str) -> str:
    """Toglie dal riassunto i pezzi che verranno riattaccati interi."""
    text = FENCE_RE.sub(" ", text)
    text = _TB_RE.sub(" ", text)
    for block in diff_blocks(text):
        text = text.replace(block, " ", 1)
    return text.strip()


def message_excerpts(message: dict) -> list[str]:
    text = _content_text(message)
    pieces = FENCE_RE.findall(text) + diff_blocks(text) + traceback_blocks(text)
    if message.get("role") == "tool" and not pieces:
        body = text.strip()
        if body:
            pieces.append(body)
    capped = []
    for piece in pieces:
        piece = piece.strip()[:EXCERPT_CHARS]
        if piece and piece not in capped:
            capped.append(piece)
    return capped


def protected_excerpts(messages: list[dict], already: str, limit: int = EXCERPT_LIMIT) -> list[str]:
    """Gli estratti più recenti. Il codice fra backtick, il diff, il traceback, il tool."""
    found: list[str] = []
    for message in reversed(messages):
        for piece in message_excerpts(message):
            if piece not in already and piece not in found:
                found.append(piece)
            if len(found) == limit:
                found.reverse()
                return found
    found.reverse()
    return found


def compact_message(content: str, max_chars: int = 500) -> str:
    prose = plain_prose(content)
    if len(prose) > max_chars:
        prose = prose[:max_chars].rstrip() + "…"
    kept = message_excerpts({"role": "user", "content": content})[:EXCERPT_LIMIT]
    if kept:
        return (prose + "\n" + "\n".join(kept)).strip()
    return prose


def extractive_summary(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        who = "Utente" if message["role"] == "user" else "Assistente"
        lines.append(f"{who}: {compact_message(message.get('content') or '', 400)}")
    text = "\n".join(lines)
    if len(text) > 1600:
        text = text[:1600].rstrip() + "…"
    return text


def code_fences(messages: list[dict], already: str) -> list[str]:
    return protected_excerpts(messages, already)


def system_prompt(card: str) -> str:
    base = (
        "Sei TramaMind, assistente personale sul computer dell'utente. "
        "Rispondi in italiano, in modo denso e concreto. "
        "Se non sai una cosa, dillo in una riga. Non riempire. "
        "Il contesto delle puntate precedenti è memoria: usalo, non ripeterlo."
    )
    card = card.strip()
    if card and not card.startswith("#"):
        base += "\n\nScheda dell'utente:\n" + card
    elif card:
        useful = "\n".join(
            line for line in card.splitlines() if line.strip() and not line.strip().startswith("#")
        ).strip()
        if useful:
            base += "\n\nScheda dell'utente:\n" + useful
    return base


def render_transcript(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        who = "Utente" if message["role"] == "user" else "Assistente"
        lines.append(f"{who}: {compact_message(message.get('content') or '', 1200)}")
    return "\n".join(lines)


def summary_prompt(previous: str, new_messages: list[dict]) -> str:
    previous = previous.strip() or "(nessuno)"
    return (
        "Riassunto precedente:\n"
        f"{previous}\n\n"
        "Nuovi scambi:\n"
        f"{render_transcript(new_messages)}\n\n"
        "Aggiorna il riassunto in italiano, in elenco breve. "
        "Conserva parola per parola blocchi di codice, numeri, nomi propri e decisioni. "
        "Non superare 180 parole. Non aggiungere fatti."
    )
