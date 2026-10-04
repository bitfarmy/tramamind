import pytest

from router.client import ChatError, Completion
from router.engine import Engine
from router.profile import fresh_profile
from router.store import blank_session


class Fake:
    def __init__(self, replies, provider="ollama"):
        self.replies = list(replies)
        self.calls = []
        self.provider = provider

    def complete(self, model, messages, timeout, max_tokens=None, on_delta=None):
        self.calls.append({"model": model, "messages": messages, "max_tokens": max_tokens})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if on_delta:
            on_delta(reply)
        return Completion(reply, model, None, None, self.provider)


def _engine(local, cloud=None, **changes):
    profile = fresh_profile("cpu16")
    for key, value in changes.items():
        setattr(profile, key, value)
    return Engine(profile, local, cloud), profile


def test_short_chat_sends_the_whole_history_and_stays_local():
    local = Fake(["Sono due, e il secondo è quello che chiedevi."])
    cloud = Fake(["non devo partire"])
    engine, _profile = _engine(local, (cloud, "groq", "m"))
    session = blank_session()
    result = engine.turn(session, "quanti sono?")
    assert result.escalated is False
    assert result.provider == "ollama"
    assert cloud.calls == []
    assert result.summarized is False
    assert session["messages"][-1]["content"].startswith("Sono due")


def test_long_chat_is_summarized_once_and_the_packet_is_smaller():
    local = Fake(["Ada ha scelto il numero 42.", "La decisione resta 42."])
    engine, profile = _engine(local, None, verbatim_turns=2, budget_tokens=2500)
    session = blank_session()
    session["messages"] = [
        {"role": "user", "content": "mi chiamo Ada"},
        {"role": "assistant", "content": "annotato"},
        {"role": "user", "content": "il numero è 42"},
        {"role": "assistant", "content": "annotato"},
    ]
    result = engine.turn(session, "che numero abbiamo scelto?")
    assert local.calls[0]["max_tokens"] == 400
    packet = local.calls[1]["messages"]
    assert "42" in packet[0]["content"] or "42" in result.text
    assert result.summarized is True
    assert result.sent_tokens < result.raw_tokens
    assert session["summary_through"] > 0


def test_weak_answer_escalates_once():
    local = Fake(["Mi dispiace, non posso aiutare."])
    cloud = Fake(["Il porto è il 20128, ed è solo locale."], provider="groq")
    engine, _profile = _engine(local, (cloud, "groq", "openai/gpt-oss-120b"))
    result = engine.turn(blank_session(), "che porta usa il router?")
    assert result.escalated is True
    assert result.provider == "groq"
    assert result.local_text.startswith("Mi dispiace")
    assert "20128" in result.text
    assert len(cloud.calls) == 1


def test_retry_skips_the_local_model():
    local = Fake(["non devo rispondere io"])
    cloud = Fake(["Risposta più precisa, con il dettaglio mancante."], provider="groq")
    engine, _profile = _engine(local, (cloud, "groq", "m"))
    session = blank_session()
    session["messages"] = [
        {"role": "user", "content": "spiega il tetto dei token"},
        {"role": "assistant", "content": "è un limite"},
    ]
    result = engine.turn(session, "rifallo meglio")
    assert local.calls == []
    assert result.escalated is True
    assert result.lane == "general"


def test_code_lane_and_local_failure():
    local = Fake([ChatError("connessione rifiutata")])
    cloud = Fake(["def somma(a, b):\n    return a + b"], provider="groq")
    engine, profile = _engine(local, (cloud, "groq", "m"))
    result = engine.turn(blank_session(), "scrivi una funzione python che somma")
    assert result.lane == "code"
    assert result.model == profile.models.code or result.provider == "groq"
    assert result.escalated is True
    assert "def somma" in result.text


def test_without_cloud_a_weak_answer_is_kept():
    local = Fake(["Mi dispiace, non posso aiutare."])
    engine, _profile = _engine(local, None)
    result = engine.turn(blank_session(), "dimmi un segreto")
    assert result.escalated is False
    assert "cloud non configurato" in (result.note or "")


def test_a_different_summary_model_is_not_loaded():
    local = Fake(["Il nome è nella scheda del contesto."])
    profile = fresh_profile("gpu12")
    profile.verbatim_turns = 1
    profile.budget_tokens = 500
    engine = Engine(profile, local, None)
    session = blank_session()
    session["messages"] = [
        {"role": "user", "content": "mi chiamo Ada e il codice è 42"},
        {"role": "assistant", "content": "annotato"},
    ]
    result = engine.turn(session, "come mi chiamo?")
    assert len(local.calls) == 1
    assert local.calls[0]["model"] == profile.models.general
    assert "Ada" in local.calls[0]["messages"][0]["content"]
    assert result.summarized is True


def test_summary_failure_falls_back_to_extractive_text():
    local = Fake([
        ChatError("modello assente"),
        "Ho tenuto il nome dal riassunto.",
    ])
    engine, _profile = _engine(local, None, verbatim_turns=1, budget_tokens=400)
    session = blank_session()
    session["messages"] = [
        {"role": "user", "content": "il progetto si chiama TramaMind e il numero è 7"},
        {"role": "assistant", "content": "ok"},
    ]
    engine.turn(session, "come si chiama?")
    packet = local.calls[1]["messages"][0]["content"]
    assert "TramaMind" in packet
