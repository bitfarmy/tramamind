"""Avvio, diagnosi, sync delle chiavi verso OmniRoute. Nessun curl in pipe."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass

from router.client import http_ok, origin
from router.keystore import canonical, detect_best_backend, get_key, mask, store_key
from router.paths import log_dir, pid_path
from router.presets import PRESETS
from router.profile import Profile, fresh_profile, load_profile, save_profile
from router.providers import PROVIDERS, resolve_provider


@dataclass
class Check:
    name: str
    level: str
    detail: str


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def checks(profile: Profile | None = None) -> list[Check]:
    profile = load_profile() if profile is None else profile
    found: list[Check] = []
    if profile is None:
        found.append(Check("profilo", "fail", "manca. `tramamind setup` oppure un preset nella pagina"))
        return found
    found.append(Check(
        "profilo",
        "ok",
        f"{profile.preset} · generale {profile.models.general} · tetto {profile.budget_tokens}",
    ))
    if shutil.which("ollama") is None:
        found.append(Check("ollama", "fail", "binario assente. https://ollama.com"))
    elif not http_ok(origin(profile.ollama_base) + "/api/version"):
        found.append(Check("ollama", "fail", "installato ma spento. `tramamind up`"))
    else:
        installed = installed_models(profile)
        found.append(Check("ollama", "ok", "in ascolto"))
        for lane, tag in (
            ("generale", profile.models.general),
            ("codice", profile.models.code),
            ("ragionamento", profile.models.think),
            ("riassunto", profile.models.summary),
        ):
            if tag in installed:
                found.append(Check(lane, "ok", tag))
            elif lane == "generale":
                found.append(Check(lane, "fail", f"{tag} non scaricato. `tramamind pull`"))
            else:
                found.append(Check(lane, "warn", f"{tag} non scaricato. `tramamind pull`"))
    _cloud_checks(profile, found)
    return found


def _cloud_checks(profile: Profile, found: list[Check]) -> None:
    escalation = profile.escalation
    if escalation.transport == "off":
        found.append(Check("escalation", "ok", "spenta"))
        return
    groq, storage = get_key("groq")
    omni = http_ok(origin(profile.omniroute_base) + "/")
    if escalation.transport in ("auto", "omniroute") and omni:
        found.append(Check("omniroute", "ok", "in ascolto"))
        found.append(Check("escalation", "ok", f"via omniroute · {escalation.model} (ID non verificato)"))
        return
    if escalation.transport == "omniroute":
        found.append(Check("omniroute", "warn", "scelto nel profilo, ma spento"))
        found.append(Check("escalation", "warn", "non disponibile"))
        return
    if groq:
        where = storage or "env"
        found.append(Check("groq", "ok", f"chiave {where}, escalation diretta"))
        found.append(Check("escalation", "ok", f"groq diretto · {escalation.model} (ID non verificato)"))
    else:
        found.append(Check(
            "escalation",
            "warn",
            "solo locale. Aggiungi una chiave Groq o avvia OmniRoute",
        ))
    if shutil.which("omniroute") and not omni:
        found.append(Check("omniroute", "warn", "installato, spento. `tramamind up`"))


def installed_models(profile: Profile) -> set[str]:
    url = origin(profile.ollama_base) + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception:
        return set()
    names = set()
    for item in body.get("models") or []:
        name = item.get("name") or ""
        names.add(name)
        if ":" in name:
            names.add(name.split(":")[0])
    needed = {
        profile.models.general,
        profile.models.code,
        profile.models.think,
        profile.models.summary,
    }
    have = set()
    for tag in needed:
        if tag in names or any(name == tag or name.startswith(tag + "-") for name in names):
            have.add(tag)
    return have


def worst_level(items: list[Check]) -> str:
    if any(item.level == "fail" for item in items):
        return "fail"
    if any(item.level == "warn" for item in items):
        return "warn"
    return "ok"


def apply_preset(preset_id: str) -> Profile:
    if preset_id not in PRESETS:
        raise ValueError(f"preset sconosciuto: {preset_id}. Usa: {', '.join(PRESETS)}")
    current = load_profile()
    if current is None:
        profile = fresh_profile(preset_id)
    else:
        fresh = fresh_profile(preset_id)
        current.preset = fresh.preset
        current.models = fresh.models
        profile = current
    save_profile(profile)
    return profile


def pull_models(profile: Profile) -> int:
    if shutil.which("ollama") is None:
        print("ollama non installato. https://ollama.com")
        return 1
    tags = []
    for tag in (
        profile.models.general,
        profile.models.code,
        profile.models.think,
        profile.models.summary,
    ):
        if tag not in tags:
            tags.append(tag)
    code = 0
    for tag in tags:
        print(f"→ ollama pull {tag}")
        result = subprocess.run(["ollama", "pull", tag])
        if result.returncode != 0:
            code = result.returncode
    return code


def sync_keys() -> list[dict]:
    if shutil.which("omniroute") is None:
        return [{
            "provider": "*",
            "ok": False,
            "detail": "omniroute non installato. La chat locale e Groq diretto funzionano lo stesso.",
        }]
    results = []
    for provider in PROVIDERS:
        key, _storage = get_key(provider.id)
        if not key:
            continue
        result = subprocess.run(
            [
                "omniroute", "setup", "--non-interactive",
                "--add-provider", "--provider", provider.id,
                "--api-key", key,
            ],
            capture_output=True, text=True,
        )
        detail = redact((result.stdout + result.stderr).strip(), [key])
        results.append({
            "provider": provider.id,
            "ok": result.returncode == 0,
            "detail": detail[-400:] or ("ok" if result.returncode == 0 else "errore"),
        })
    if not results:
        results.append({"provider": "*", "ok": False, "detail": "nessuna chiave da sincronizzare"})
    return results


def save_provider_key(name: str, key: str) -> tuple[str, str]:
    provider = resolve_provider(name)
    if provider is None or provider.id == "omniroute" and name not in ("omniroute", "endpoint"):
        raise ValueError(f"provider sconosciuto: {name}")
    if not key.strip():
        raise ValueError("chiave vuota")
    backend = detect_best_backend()
    store_key(canonical(name), key.strip(), backend)
    return canonical(name), backend


def key_status() -> list[dict]:
    rows = []
    for provider in list(PROVIDERS) + [resolve_provider("omniroute")]:
        key, storage = get_key(provider.id)
        rows.append({
            "id": provider.id,
            "label": provider.label,
            "url": provider.url,
            "storage": storage,
            "masked": mask(key) if key else "",
            "present": bool(key),
        })
    return rows


def _read_pids() -> dict:
    path = pid_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_pids(pids: dict) -> None:
    pid_path().write_text(json.dumps(pids), encoding="utf-8")


def _spawn(argv: list[str], env_extra: dict | None, log_name: str) -> int:
    log = log_dir() / f"{log_name}.log"
    handle = open(log, "ab")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        argv,
        stdout=handle,
        stderr=handle,
        start_new_session=True,
        env=env,
    )
    return proc.pid


def _wait_until(url: str, attempts: int) -> bool:
    for _ in range(attempts):
        if http_ok(url, timeout=1.5):
            return True
        time.sleep(1)
    return False


def up(profile: Profile, *, router: bool = False) -> list[str]:
    notes = []
    pids = _read_pids()
    ollama_health = origin(profile.ollama_base) + "/api/version"
    if shutil.which("ollama") is None:
        notes.append("ollama assente: installalo da https://ollama.com e rilancia `tramamind up`")
    elif http_ok(ollama_health):
        notes.append("ollama già attivo")
    else:
        pid = _spawn(["ollama", "serve"], None, "ollama")
        if _wait_until(ollama_health, 20):
            pids["ollama"] = pid
            notes.append(f"ollama avviato (pid {pid})")
        else:
            notes.append("ollama non ha risposto. Vedi i log in ~/.local/share/tramamind/logs")
    want_router = router or _any_cloud_key()
    omni_health = origin(profile.omniroute_base) + "/"
    if not want_router:
        notes.append("omniroute non richiesto: nessuna chiave cloud")
    elif shutil.which("omniroute") is None:
        notes.append("omniroute non installato. L'escalation Groq diretta resta disponibile")
    elif http_ok(omni_health):
        notes.append("omniroute già attivo")
    else:
        pid = _spawn(
            ["omniroute", "--no-open"],
            {
                "OMNIROUTE_MEMORY_MB": str(profile.omniroute_memory_mb),
                "REQUIRE_API_KEY": "false",
                "HOSTNAME": "127.0.0.1",
                "PORT": "20128",
            },
            "omniroute",
        )
        if _wait_until(omni_health, 30):
            pids["omniroute"] = pid
            notes.append(f"omniroute avviato (pid {pid}, heap {profile.omniroute_memory_mb} MB)")
        else:
            notes.append("omniroute non ha risposto. La chat locale non dipende da lui")
    _write_pids(pids)
    return notes


def _any_cloud_key() -> bool:
    return any(get_key(provider.id)[0] for provider in PROVIDERS)


def down() -> list[str]:
    notes = []
    pids = _read_pids()
    for name, pid in list(pids.items()):
        if not pid:
            continue
        try:
            os.kill(int(pid), 15)
            notes.append(f"fermato {name} (pid {pid})")
        except ProcessLookupError:
            notes.append(f"{name} era già fermo")
        except OSError as exc:
            notes.append(f"{name}: {exc}")
    _write_pids({})
    if not notes:
        notes.append("nessun processo avviato da tramamind")
    return notes


def probe(profile: Profile) -> str:
    from router.client import HttpChatClient
    client = HttpChatClient(profile.ollama_base, "ollama")
    completion = client.complete(
        profile.models.general,
        [{"role": "user", "content": "Rispondi solo: ok"}],
        timeout=int(profile.timeouts.get("local", 180)),
        max_tokens=20,
    )
    return completion.text.strip()
