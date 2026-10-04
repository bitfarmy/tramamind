"""Un turno: pacchetto con tetto, modello locale, al massimo una escalation."""
from __future__ import annotations

import time
from dataclasses import dataclass

from router import packet, store
from router.client import ChatError, HttpChatClient, http_ok, origin
from router.keystore import get_key
from router.packet import groq_model, omni_model
from router.profile import Profile
from router.providers import GROQ_BASE


@dataclass
class TurnResult:
    text: str
    local_text: str | None
    model: str
    provider: str
    lane: str
    escalated: bool
    escalation_reason: str | None
    raw_tokens: int
    sent_tokens: int
    prompt_tokens: int | None
    completion_tokens: int | None
    summarized: bool
    latency_ms: int
    session_id: str
    note: str | None = None


def format_turn(result: TurnResult) -> str:
    route = result.provider
    if result.escalated and result.local_text is not None:
        route = f"locale → {result.provider}"
    elif result.escalated:
        route = result.provider
    else:
        route = "locale"
    bits = [route, result.model, f"{result.latency_ms} ms"]
    if result.prompt_tokens is not None:
        bits.append(f"inviati {result.prompt_tokens} (api)")
        bits.append(f"stima pacchetto {result.sent_tokens}")
    else:
        bits.append(f"inviati ~{result.sent_tokens}")
    if result.summarized and result.raw_tokens > result.sent_tokens:
        saved = round(100 * (result.raw_tokens - result.sent_tokens) / result.raw_tokens)
        bits.append(f"storia intera ~{result.raw_tokens}")
        bits.append(f"−{saved}% sul pacchetto")
    elif not result.summarized:
        bits.append("storia nel tetto")
    if result.escalation_reason:
        bits.append(result.escalation_reason)
    if result.note:
        bits.append(result.note)
    return " · ".join(bits)


class Engine:
    def __init__(self, profile: Profile, local: HttpChatClient | None = None, cloud="auto"):
        self.profile = profile
        self.local = local or HttpChatClient(profile.ollama_base, "ollama")
        # "auto" interroga OmniRoute e la chiave Groq. None spegne il cloud.
        if cloud == "auto":
            self._cloud = None
            self._cloud_resolved = False
        else:
            self._cloud = cloud
            self._cloud_resolved = True

    def turn(
        self,
        session: dict,
        user_text: str,
        *,
        lane: str | None = None,
        on_delta=None,
        on_notice=None,
        debug=None,
    ) -> TurnResult:
        started = time.perf_counter()
        history = list(session.get("messages") or [])
        user_message = {"role": "user", "content": user_text}
        pending = history + [user_message]
        retry = packet.wants_retry(user_text)
        chosen = lane or _lane_for(pending, retry)
        system = packet.system_prompt(store.read_card())
        summary, head_len = self._summary_for(session, pending, system, self._model(chosen))
        fences = packet.code_fences(pending[:head_len], summary) if head_len else []
        built = packet.build_packet(
            history=pending,
            system=system,
            summary=summary if head_len else "",
            budget=self.profile.budget_tokens,
            verbatim=self.profile.verbatim_turns,
            fences=fences,
        )
        if debug:
            debug(built["messages"], built)
        cloud = self._cloud_client()
        local_text = None
        note = None
        reason = None
        completion = None
        provider = "ollama"
        model = self._model(chosen)

        if retry:
            reason = "richiesta"
            if cloud is not None and on_notice:
                on_notice("provo il cloud")
            completion, provider, model, note = self._escalate(cloud, built, chosen, on_delta)
            if completion is None:
                note = note or "cloud non configurato, resto sul locale"
                reason = None
                completion = self._complete_local(built, model, on_delta)
                provider = "ollama"
        else:
            try:
                completion = self._complete_local(built, model, on_delta)
            except ChatError as exc:
                reason = "locale irraggiungibile"
                if cloud is not None and on_notice:
                    on_notice("locale irraggiungibile, provo il cloud")
                completion, provider, model, note = self._escalate(cloud, built, chosen, on_delta)
                if completion is None:
                    raise ChatError(str(exc)) from exc
            if completion is not None and reason is None and packet.is_weak(completion.text):
                local_text = completion.text
                reason = "risposta debole"
                if cloud is not None and on_notice:
                    on_notice("risposta debole, provo il cloud")
                escalated, provider, model, note = self._escalate(cloud, built, chosen, on_delta)
                if escalated is None:
                    note = note or "cloud non configurato"
                    reason = None
                else:
                    completion = escalated

        assert completion is not None
        text = completion.text
        assistant = {"role": "assistant", "content": text}
        session["messages"] = pending + [assistant]
        if not session.get("title"):
            session["title"] = user_text.strip().splitlines()[0][:60]
        if built["summarized"]:
            session["summary"] = built.get("summary") or summary
            session["summary_through"] = built["head_len"]
        store.save_session(session)
        self._log(session, chosen, completion, built, reason, started)
        return TurnResult(
            text=text,
            local_text=local_text,
            model=completion.model or model,
            provider=provider,
            lane=chosen,
            escalated=provider != "ollama",
            escalation_reason=reason if provider != "ollama" else None,
            raw_tokens=built["raw_tokens"],
            sent_tokens=built["sent_tokens"],
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            summarized=built["summarized"],
            latency_ms=int((time.perf_counter() - started) * 1000),
            session_id=session["id"],
            note=note,
        )

    def _model(self, lane: str) -> str:
        models = self.profile.models
        return {
            "code": models.code,
            "think": models.think,
            "fast": models.summary,
        }.get(lane, models.general)

    def _complete_local(self, built: dict, model: str, on_delta):
        timeout = int(self.profile.timeouts.get("local", 180))
        return self.local.complete(model, _wire(built["messages"]), timeout, on_delta=on_delta)

    def _escalate(self, cloud, built, lane, on_delta):
        if cloud is None:
            return None, "ollama", self._model(lane), "cloud non configurato"
        client, provider, model = cloud
        timeout = int(self.profile.timeouts.get("cloud", 90))
        try:
            completion = client.complete(model, _wire(built["messages"]), timeout, on_delta=on_delta)
        except ChatError as exc:
            return None, provider, model, f"cloud non ha risposto ({exc})"
        completion.provider = provider
        return completion, provider, model, None

    def _summary_for(self, session: dict, pending: list[dict], system: str, lane_model: str) -> tuple[str, int]:
        head, _tail = packet.split_history(
            pending,
            self.profile.budget_tokens,
            self.profile.verbatim_turns,
            system,
        )
        if not head:
            return "", 0
        through = int(session.get("summary_through") or 0)
        previous = session.get("summary") or ""
        if through == len(head) and previous:
            return previous, len(head)
        fresh = head[through:] if 0 <= through < len(head) else head
        if through > len(head):
            fresh = head
            previous = ""
        produced = self._summarize(previous, fresh, lane_model)
        return produced, len(head)

    def _summarize(self, previous: str, messages: list[dict], lane_model: str) -> str:
        # Un secondo tag farebbe scaricare e ricaricare il modello a ogni turno.
        if self.profile.models.summary != lane_model:
            return packet.extractive_summary(messages)
        prompt = packet.summary_prompt(previous, messages)
        messages_out = [
            {"role": "system", "content": "Riassumi senza aggiungere fatti."},
            {"role": "user", "content": prompt},
        ]
        model = self.profile.models.summary
        timeout = int(self.profile.timeouts.get("summary", 45))
        try:
            completion = self.local.complete(
                model, messages_out, timeout, max_tokens=400
            )
            text = completion.text.strip()
            if text:
                return text
        except ChatError:
            pass
        return packet.extractive_summary(messages)

    def _cloud_client(self):
        if self._cloud_resolved:
            return self._cloud
        self._cloud_resolved = True
        self._cloud = resolve_cloud(self.profile)
        return self._cloud

    def _log(self, session, lane, completion, built, reason, started) -> None:
        from router.stats import append_log
        append_log({
            "ts": time.time(),
            "session": session["id"],
            "lane": lane,
            "model": completion.model,
            "provider": completion.provider,
            "packet_tokens_est": built["sent_tokens"],
            "raw_tokens_est": built["raw_tokens"],
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "escalated": bool(reason and completion.provider != "ollama"),
            "reason": reason,
            "summarized": built["summarized"],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        })


def _lane_for(pending: list[dict], retry: bool) -> str:
    if retry:
        users = [m["content"] for m in pending[:-1] if m["role"] == "user"]
        if users:
            return packet.classify(users[-1])
    return packet.classify(pending[-1]["content"])


def _wire(messages: list[dict]) -> list[dict]:
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def resolve_cloud(profile: Profile):
    """Ritorna (client, provider, model) oppure None. Non inventa un router."""
    escalation = profile.escalation
    if escalation.transport == "off" or not escalation.model.strip():
        return None
    model = escalation.model.strip()
    omni_up = False
    if escalation.transport in ("auto", "omniroute"):
        omni_up = http_ok(origin(profile.omniroute_base) + "/")
    if escalation.transport in ("auto", "omniroute") and omni_up:
        key, _storage = get_key("omniroute")
        client = HttpChatClient(profile.omniroute_base, "omniroute", key)
        return client, "omniroute", omni_model(model)
    groq_key, _storage = get_key("groq")
    if escalation.transport in ("auto", "groq") and groq_key:
        client = HttpChatClient(GROQ_BASE, "groq", groq_key)
        return client, "groq", groq_model(model)
    return None
