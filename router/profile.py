"""Profilo unico: modelli, tetto token, dove sta l'escalation."""
from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, Field

from router.paths import profile_path
from router.presets import PRESETS, Preset


class Models(BaseModel):
    general: str
    code: str
    think: str
    summary: str


class Escalation(BaseModel):
    # auto: OmniRoute se è su, altrimenti Groq diretto se c'è la chiave.
    transport: Literal["auto", "omniroute", "groq", "off"] = "auto"
    # ID sul filo di Groq. OmniRoute riceve il prefisso groq/ quando manca.
    model: str = "openai/gpt-oss-120b"


class Profile(BaseModel):
    version: int = 1
    preset: str = "cpu16"
    models: Models
    budget_tokens: int = 2500
    verbatim_turns: int = 6
    # ollama: il proxy inoltra a ollama_base. omniroute: a omniroute_base.
    proxy_upstream: Literal["ollama", "omniroute"] = "ollama"
    ollama_base: str = "http://127.0.0.1:11434/v1"
    omniroute_base: str = "http://127.0.0.1:20128/v1"
    omniroute_memory_mb: int = 1024
    escalation: Escalation = Field(default_factory=Escalation)
    timeouts: dict[str, int] = Field(
        default_factory=lambda: {"local": 180, "summary": 45, "cloud": 90}
    )


def models_from_preset(preset: Preset) -> Models:
    return Models(
        general=preset.general,
        code=preset.code,
        think=preset.think,
        summary=preset.summary,
    )


def fresh_profile(preset_id: str) -> Profile:
    preset = PRESETS[preset_id]
    return Profile(preset=preset.id, models=models_from_preset(preset))


def dump_profile(profile: Profile) -> str:
    models = profile.models
    escalation = profile.escalation
    return (
        f"version: {profile.version}\n"
        f"preset: {profile.preset}\n"
        "models:\n"
        f"  general: {models.general}\n"
        f"  code: {models.code}\n"
        f"  think: {models.think}\n"
        f"  summary: {models.summary}\n"
        f"budget_tokens: {profile.budget_tokens}\n"
        f"verbatim_turns: {profile.verbatim_turns}\n"
        f"proxy_upstream: {profile.proxy_upstream}\n"
        f"ollama_base: {profile.ollama_base}\n"
        f"omniroute_base: {profile.omniroute_base}\n"
        f"omniroute_memory_mb: {profile.omniroute_memory_mb}\n"
        "escalation:\n"
        f"  transport: {escalation.transport}\n"
        f"  model: {escalation.model}\n"
        "timeouts:\n"
        f"  local: {profile.timeouts.get('local', 180)}\n"
        f"  summary: {profile.timeouts.get('summary', 45)}\n"
        f"  cloud: {profile.timeouts.get('cloud', 90)}\n"
    )


def save_profile(profile: Profile) -> None:
    profile_path().write_text(dump_profile(profile), encoding="utf-8")


def load_profile() -> Profile | None:
    path = profile_path()
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Profile.model_validate(data)


def require_profile() -> Profile:
    profile = load_profile()
    if profile is None:
        raise FileNotFoundError(
            "Profilo assente. Esegui `tramamind setup` oppure scegli un preset dalla pagina."
        )
    return profile
