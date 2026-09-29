"""
TramaMind — storage chiavi a tre livelli.

Cascata di risoluzione (vedi docs/cloud-implementation.md):
  1. keyring di sistema   (solo dove esiste un backend: desktop)
  2. file cifrato age     (~/.config/tramamind/secrets.age — consigliato su server)
  3. .env plain           (~/.config/tramamind/.env — solo sviluppo)
  4. variabili ambiente   (Docker, CI) — gestita dal chiamante

Nessuna chiave passa mai per file versionati.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SERVICE_NAME = "tramamind"
CONFIG_DIR = Path.home() / ".config" / "tramamind"
PLAIN_ENV_FILE = CONFIG_DIR / ".env"
AGE_SECRETS = CONFIG_DIR / "secrets.age"
AGE_IDENTITY = CONFIG_DIR / "age-identity.txt"


def env_var_name(provider: str) -> str:
    return f"{provider.upper()}_API_KEY"


# ── Backend: keyring ─────────────────────────────────────────

def keyring_available() -> bool:
    """True solo se esiste un backend keyring reale (non su Linux headless)."""
    try:
        import keyring
        backend_name = type(keyring.get_keyring()).__name__.lower()
        return "fail" not in backend_name and "null" not in backend_name
    except Exception:
        return False


def _keyring_get(provider: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(SERVICE_NAME, provider)
    except Exception:
        return None


def _keyring_set(provider: str, key: str) -> None:
    import keyring
    keyring.set_password(SERVICE_NAME, provider, key)


def _keyring_delete(provider: str) -> None:
    try:
        import keyring
        keyring.delete_password(SERVICE_NAME, provider)
    except Exception:
        pass


# ── Backend: age ─────────────────────────────────────────────

def age_available() -> bool:
    return shutil.which("age") is not None and shutil.which("age-keygen") is not None


def _age_ensure_identity() -> str:
    """Crea l'identità age se manca; ritorna il recipient pubblico."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not AGE_IDENTITY.exists():
        out = subprocess.run(
            ["age-keygen", "-o", str(AGE_IDENTITY)],
            check=True, capture_output=True, text=True,
        )
        AGE_IDENTITY.chmod(0o600)
        recipient = out.stderr.strip().splitlines()[-1].split()[-1]
        return recipient
    for line in AGE_IDENTITY.read_text().splitlines():
        if line.startswith("# public key:"):
            return line.split(":")[-1].strip()
    raise RuntimeError(f"recipient non trovato in {AGE_IDENTITY}")


def _age_read_all() -> dict[str, str]:
    if not AGE_SECRETS.exists():
        return {}
    out = subprocess.run(
        ["age", "-d", "-i", str(AGE_IDENTITY), str(AGE_SECRETS)],
        check=True, capture_output=True, text=True,
    )
    return _parse_dotenv(out.stdout)


def _age_write_all(entries: dict[str, str]) -> None:
    recipient = _age_ensure_identity()
    body = "\n".join(f"{k}={v}" for k, v in sorted(entries.items())) + "\n"
    tmp = AGE_SECRETS.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        subprocess.run(["age", "-r", recipient], input=body.encode(),
                       stdout=fh, check=True)
    tmp.replace(AGE_SECRETS)
    AGE_SECRETS.chmod(0o600)


def _age_get(provider: str) -> str | None:
    try:
        return _age_read_all().get(env_var_name(provider))
    except Exception:
        return None


def _age_set(provider: str, key: str) -> None:
    entries = _age_read_all()
    entries[env_var_name(provider)] = key
    _age_write_all(entries)


def _age_delete(provider: str) -> None:
    entries = _age_read_all()
    if entries.pop(env_var_name(provider), None) is not None:
        _age_write_all(entries)


# ── Backend: .env plain ──────────────────────────────────────

def _parse_dotenv(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _plain_read_all() -> dict[str, str]:
    if not PLAIN_ENV_FILE.exists():
        return {}
    return _parse_dotenv(PLAIN_ENV_FILE.read_text())


def _plain_write_all(entries: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}={v}" for k, v in sorted(entries.items())) + "\n"
    PLAIN_ENV_FILE.write_text(body)
    PLAIN_ENV_FILE.chmod(0o600)


def _plain_get(provider: str) -> str | None:
    return _plain_read_all().get(env_var_name(provider))


def _plain_set(provider: str, key: str) -> None:
    entries = _plain_read_all()
    entries[env_var_name(provider)] = key
    _plain_write_all(entries)


def _plain_delete(provider: str) -> None:
    entries = _plain_read_all()
    if entries.pop(env_var_name(provider), None) is not None:
        _plain_write_all(entries)


# ── API pubblica ─────────────────────────────────────────────

BACKENDS = ("keyring", "age", "plain")


def detect_best_backend() -> str:
    """Scelta automatica: keyring su desktop, age su server, plain come fallback."""
    if keyring_available():
        return "keyring"
    if age_available():
        return "age"
    return "plain"


def store_key(provider: str, key: str, backend: str) -> None:
    if backend == "keyring":
        _keyring_set(provider, key)
    elif backend == "age":
        _age_set(provider, key)
    elif backend == "plain":
        _plain_set(provider, key)
    else:
        raise ValueError(f"backend sconosciuto: {backend}")


def get_key(provider: str) -> tuple[str | None, str | None]:
    """Ritorna (chiave, storage) seguendo la cascata. storage=None se non trovata."""
    if keyring_available():
        key = _keyring_get(provider)
        if key:
            return key, "keyring"
    key = _age_get(provider)
    if key:
        return key, "age"
    key = _plain_get(provider)
    if key:
        return key, "plain"
    env = os.getenv(env_var_name(provider))
    if env:
        return env, "env"
    return None, None


def delete_key(provider: str) -> list[str]:
    """Rimuove la chiave da tutti gli storage. Ritorna gli storage svuotati."""
    removed = []
    if keyring_available() and _keyring_get(provider):
        _keyring_delete(provider)
        removed.append("keyring")
    if _age_get(provider):
        _age_delete(provider)
        removed.append("age")
    if _plain_get(provider):
        _plain_delete(provider)
        removed.append("plain")
    return removed


def mask(key: str) -> str:
    return "•" * 8 + key[-4:] if len(key) > 4 else "•" * 8
