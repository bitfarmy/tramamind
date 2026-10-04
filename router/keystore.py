"""
Storage chiavi a tre livelli.

Cascata: keyring di sistema, file cifrato age, .env con permessi 0600,
variabile d'ambiente. Nessuna chiave finisce in un file versionato.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from router.paths import config_dir
from router.providers import resolve_provider

SERVICE_NAME = "tramamind"


def plain_env_file():
    return config_dir() / ".env"


def age_secrets():
    return config_dir() / "secrets.age"


def age_identity():
    return config_dir() / "age-identity.txt"


def canonical(provider: str) -> str:
    found = resolve_provider(provider)
    return found.id if found else provider.strip().lower()


def lookup_names(provider: str) -> list[str]:
    found = resolve_provider(provider)
    if found is None:
        return [provider.strip().lower()]
    names = [found.id, *found.aliases]
    seen = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


def env_var_name(provider: str) -> str:
    found = resolve_provider(provider)
    if found is not None:
        return found.env_key
    return f"{canonical(provider).upper()}_API_KEY"


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


def age_available() -> bool:
    return shutil.which("age") is not None and shutil.which("age-keygen") is not None


def _age_ensure_identity() -> str:
    """Crea l'identità age se manca e ritorna il recipient pubblico."""
    identity = age_identity()
    config_dir().mkdir(parents=True, exist_ok=True)
    if not identity.exists():
        out = subprocess.run(
            ["age-keygen", "-o", str(identity)],
            check=True, capture_output=True, text=True,
        )
        identity.chmod(0o600)
        return out.stderr.strip().splitlines()[-1].split()[-1]
    for line in identity.read_text(encoding="utf-8").splitlines():
        if line.startswith("# public key:"):
            return line.split(":")[-1].strip()
    raise RuntimeError(f"recipient non trovato in {identity}")


def _age_read_all() -> dict[str, str]:
    secrets = age_secrets()
    if not secrets.exists():
        return {}
    out = subprocess.run(
        ["age", "-d", "-i", str(age_identity()), str(secrets)],
        check=True, capture_output=True, text=True,
    )
    return _parse_dotenv(out.stdout)


def _age_write_all(entries: dict[str, str]) -> None:
    recipient = _age_ensure_identity()
    body = "\n".join(f"{key}={value}" for key, value in sorted(entries.items())) + "\n"
    tmp = age_secrets().with_suffix(".tmp")
    with open(tmp, "wb") as handle:
        subprocess.run(
            ["age", "-r", recipient], input=body.encode(), stdout=handle, check=True
        )
    tmp.replace(age_secrets())
    age_secrets().chmod(0o600)


def _age_get(name: str) -> str | None:
    try:
        return _age_read_all().get(env_var_name(name))
    except Exception:
        return None


def _age_set(name: str, key: str) -> None:
    entries = _age_read_all()
    entries[env_var_name(name)] = key
    _age_write_all(entries)


def _age_delete(name: str) -> None:
    entries = _age_read_all()
    if entries.pop(env_var_name(name), None) is not None:
        _age_write_all(entries)


def _parse_dotenv(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _plain_read_all() -> dict[str, str]:
    path = plain_env_file()
    if not path.exists():
        return {}
    return _parse_dotenv(path.read_text(encoding="utf-8"))


def _plain_write_all(entries: dict[str, str]) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{key}={value}" for key, value in sorted(entries.items())) + "\n"
    path = plain_env_file()
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)


def _plain_get(name: str) -> str | None:
    return _plain_read_all().get(env_var_name(name))


def _plain_set(name: str, key: str) -> None:
    entries = _plain_read_all()
    entries[env_var_name(name)] = key
    _plain_write_all(entries)


def _plain_delete(name: str) -> None:
    entries = _plain_read_all()
    if entries.pop(env_var_name(name), None) is not None:
        _plain_write_all(entries)


BACKENDS = ("keyring", "age", "plain")


def detect_best_backend() -> str:
    if keyring_available():
        return "keyring"
    if age_available():
        return "age"
    return "plain"


def store_key(provider: str, key: str, backend: str) -> None:
    name = canonical(provider)
    if backend == "keyring":
        _keyring_set(name, key)
    elif backend == "age":
        _age_set(name, key)
    elif backend == "plain":
        _plain_set(name, key)
    else:
        raise ValueError(f"backend sconosciuto: {backend}")


def get_key(provider: str) -> tuple[str | None, str | None]:
    """Ritorna (chiave, storage). Controlla anche gli alias storici, per esempio kimi."""
    names = lookup_names(provider)
    if keyring_available():
        for name in names:
            key = _keyring_get(name)
            if key:
                return key, "keyring"
    for name in names:
        key = _age_get(name)
        if key:
            return key, "age"
    for name in names:
        key = _plain_get(name)
        if key:
            return key, "plain"
    for name in names:
        env = os.getenv(env_var_name(name))
        if env:
            return env, "env"
    return None, None


def delete_key(provider: str) -> list[str]:
    removed = []
    for name in lookup_names(provider):
        if keyring_available() and _keyring_get(name):
            _keyring_delete(name)
            if "keyring" not in removed:
                removed.append("keyring")
        if _age_get(name):
            _age_delete(name)
            if "age" not in removed:
                removed.append("age")
        if _plain_get(name):
            _plain_delete(name)
            if "plain" not in removed:
                removed.append("plain")
    return removed


def mask(key: str) -> str:
    return "•" * 8 + key[-4:] if len(key) > 4 else "•" * 8
