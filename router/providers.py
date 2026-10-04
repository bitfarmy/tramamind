"""Catalogo provider che TramaMind sa spingere. Niente ID modello inventati."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    id: str
    env_key: str
    label: str
    url: str
    aliases: tuple[str, ...] = ()


PROVIDERS: tuple[Provider, ...] = (
    Provider("google", "GOOGLE_API_KEY", "Google AI Studio", "https://aistudio.google.com/apikey"),
    Provider("groq", "GROQ_API_KEY", "Groq", "https://console.groq.com/keys"),
    Provider("nvidia", "NVIDIA_API_KEY", "NVIDIA NIM", "https://build.nvidia.com"),
    Provider("cerebras", "CEREBRAS_API_KEY", "Cerebras", "https://cloud.cerebras.ai"),
    Provider("openrouter", "OPENROUTER_API_KEY", "OpenRouter", "https://openrouter.ai/keys"),
    Provider("moonshot", "KIMI_API_KEY", "Kimi (Moonshot)", "https://platform.moonshot.ai", ("kimi",)),
)

# Chiave che i client mandano a OmniRoute, se il processo la richiede.
OMNIROUTE_KEY = Provider("omniroute", "OMNIROUTE_API_KEY", "OmniRoute (client)", "")

GROQ_BASE = "https://api.groq.com/openai/v1"


def resolve_provider(name: str) -> Provider | None:
    key = name.strip().lower()
    if key in (OMNIROUTE_KEY.id, "endpoint"):
        return OMNIROUTE_KEY
    for provider in PROVIDERS:
        if key == provider.id or key in provider.aliases:
            return provider
    return None


def provider_ids() -> list[str]:
    return [provider.id for provider in PROVIDERS]
