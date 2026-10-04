"""Percorsi XDG. Si leggono a ogni chiamata, così i test possono isolarli."""
from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    override = os.environ.get("TRAMAMIND_CONFIG_DIR")
    path = Path(override) if override else Path.home() / ".config" / "tramamind"
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    override = os.environ.get("TRAMAMIND_DATA_DIR")
    path = Path(override) if override else Path.home() / ".local" / "share" / "tramamind"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_path() -> Path:
    return config_dir() / "profile.yaml"


def card_path() -> Path:
    return config_dir() / "card.md"


def session_dir() -> Path:
    path = data_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "requests.jsonl"


def pid_path() -> Path:
    return data_dir() / "pids.json"


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
