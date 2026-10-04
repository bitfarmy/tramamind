"""Modelli Ollama verificabili, gli stessi di docs/local-models.md.

Il riassunto usa sempre un modello piccolo: non si spreca un 32B per
accorciare la chat precedente.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    general: str
    code: str
    think: str
    summary: str


PRESETS: dict[str, Preset] = {
    "cpu16": Preset(
        "cpu16",
        "CPU o GPU integrata, 16 GB di RAM",
        general="gemma3:4b",
        code="qwen2.5-coder:3b",
        think="deepseek-r1:1.5b",
        summary="gemma3:4b",
    ),
    "gpu12": Preset(
        "gpu12",
        "GPU da circa 12 GB",
        general="qwen3:8b",
        code="qwen2.5-coder:7b",
        think="deepseek-r1:8b",
        summary="gemma3:4b",
    ),
    "gpu24": Preset(
        "gpu24",
        "GPU da 24 GB",
        general="qwen3:32b",
        code="qwen2.5-coder:14b",
        think="deepseek-r1:14b",
        summary="gemma3:4b",
    ),
}


def suggest_preset(ram_gb: float | None = None) -> str:
    """La RAM di sistema non è VRAM: un PC con tanta RAM resta su modelli da 8B."""
    if ram_gb is None:
        ram_gb = _ram_gb()
    if ram_gb >= 24:
        return "gpu12"
    return "cpu16"


def _ram_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / 1024 / 1024
    except OSError:
        pass
    return 0.0
