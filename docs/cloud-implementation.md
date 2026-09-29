# TramaMind Cloud — Implementazione ibrida Oracle + PC locale

## Stato: Specifica approvata — Settembre 2026

Estensione di TramaMind con un **nodo cloud gratuito su Oracle** (hub sempre
attivo) e il PC locale come **edge** per i modelli grandi.
`NODE_ROLE=standalone` mantiene il comportamento originale su nodo singolo.

| Problema | Soluzione |
|----------|-----------|
| PC spento = TramaMind offline | Oracle sempre attivo, accessibile da telefono/tablet |
| Distillati piccoli occupano risorse PC | Spostati su Oracle (4B invece di 26B) |
| Avvio lento modelli grandi | Oracle mantiene caldo un modello leggero |
| API key sparse in `.env` | Gestione centralizzata via CLI + keyring/age |

---

## 1. Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                     ORACLE CLOUD (HUB)                      │
│                  Ampere A1 — 2 OCPU / 12 GB                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  OmniRoute   │  │ Entropy Gate │  │ vLLM (Qwen3-4B)  │   │
│  │  porta 20128 │  │  porta 9090  │  │   porta 8000     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              API Gratuite (L3B)                        │ │
│  │  Google → Groq → NVIDIA → Cerebras → OpenRouter → Kimi │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ▲
                  Tailscale (default) o HTTPS+token (opz.)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      PC LOCALE (EDGE)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Desktop    │  │    Ollama    │  │  Modelli grandi  │   │
│  │   (client)   │  │  porta 11434 │  │ Gemopus 26B      │   │
│  └──────────────┘  └──────────────┘  │ Qwopus 27B       │   │
│                                      └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Flusso richiesta

1. Il client (desktop, OpenClaw/Telegram, CLI) invia la richiesta a OmniRoute sull'hub
2. OmniRoute classifica il task e verifica i modelli disponibili
3. **Task semplice** → Qwen3-4B locale su Oracle (latenza ~0, costo 0)
4. **Task complesso + PC online** → instrada all'edge (Gemopus 26B / Qwopus 27B)
5. **PC offline** → fallback API cloud gratuite
6. Risposta → Entropy Gate (quenching + cache semantica) → client, con provenienza

---

## 2. Limiti Oracle Free Tier

| Risorsa | Limite | Utilizzo TramaMind |
|---------|--------|-------------------|
| Ampere A1 | 2 OCPU / 12 GB RAM | vLLM 4B + servizi |
| Storage | 200 GB totali | 100 GB boot volume: modelli + log + cache |
| Egress | 10 TB/mese | Mai raggiungibile per uso personale |
| IP pubblico | 1 incluso | Statico, assegnato alla VM |

> Dal 15 giugno 2026 i limiti Always Free sono 2 OCPU/12 GB (prima 4/24).
> Budget alert a 1 $ obbligatorio. Dettagli: [oracle-free-tier.md](oracle-free-tier.md)

---

## 3. Stack tecnico

### Hub (Oracle) — budget RAM 12 GB

| Componente | Tecnologia | RAM |
|------------|-----------|-----|
| Sistema + Docker | Ubuntu 24.04 ARM64 | ~2 GB |
| vLLM + GPT-5-Distill-Qwen3-4B (Q4) | CPU backend, ctx 8k | ~4 GB |
| Entropy Gate | Python 3.10 | ~1 GB |
| OmniRoute | :20128 | ~0.5 GB |
| Buffer | — | ~4.5 GB |

Modelli hub: **GPT-5-Distill-Qwen3-4B** (primario), **Gemini3.5-Code-Reasoner-2B**
(fast lane/heartbeat). Esclusi: Qwen3.5-9B (budget RAM), 26B/27B (solo edge).

⚠️ **vLLM su ARM64**: l'immagine ufficiale `vllm/vllm-openai` è x86-only.
Su A1.Flex: build da sorgente con backend CPU, oppure fallback documentato
a Ollama/llama.cpp con gli stessi pesi (vedi `scripts/oracle-setup.sh`).

### Edge (PC)

| Componente | Note |
|------------|------|
| Ollama :11434 | modelli >13B, `keep_alive: 30m` |
| Gemopus 26B, Qwopus 27B | solo quando il PC è acceso |
| Desktop (fork Berd) | punta all'hub via Tailscale |

---

## 4. Rete e sicurezza

**Default: Tailscale-only.** Hub ed edge si parlano sull'overlay WireGuard,
zero porte esposte oltre SSH. Il token edge resta come autenticazione
applicativa (difesa in profondità).

**Opzione pubblica (alternativa)**: Caddy come reverse proxy TLS con dominio
proprio (`https://tramamind-hub.tuodominio.it`) + token obbligatorio su ogni
endpoint. Da scegliere solo se serve accesso da dispositivi senza Tailscale.
In quel caso aprire solo 80/443 nella Security List OCI — mai 20128/9090/8000.

Token e segreti condivisi: `~/.config/tramamind/auth.yaml` cifrato con **age**.

---

## 5. Gestione API key — tre livelli ✅ (fase 2 implementata)

```
1. Keyring di sistema (consigliato su desktop)
   macOS Keychain · Linux Secret Service · Windows Credential Manager
2. File cifrato age/gpg (consigliato su server headless, es. hub Oracle)
   ~/.config/tramamind/secrets.age
3. .env plain (solo sviluppo, gitignored)
```

⚠️ Su Linux headless il keyring non ha backend: la cascata parte dal livello 2.
La CLI lo rileva e propone automaticamente l'opzione giusta.

### CLI: `tramamind keys` (implementata: `cli/keys.py`)

```bash
pip install -e .
tramamind keys setup          # wizard interattivo tutti i provider
tramamind keys add google     # singola chiave
tramamind keys list           # stato: presente/mancante + storage (mascherata)
tramamind keys remove google  # rimozione da tutti gli storage
```

I provider vengono letti da [router/providers.yaml](../router/providers.yaml):
nessun elenco hardcoded. Validazione leggera dei prefissi noti (AIza, gsk_,
nvapi-, sk-or-…) con warning non bloccante.

### Risoluzione runtime (implementata: `router/config.py`)

```python
from router.config import get_settings
settings = get_settings()              # TRAMAMIND_NODE_ROLE/HUB_URL/EDGE_TOKEN
key = settings.get_api_key("groq")     # keyring → age → .env → env
```

---

## 6. Configurazione nodi

### Hub — `~/.config/tramamind/config.yaml`

```yaml
node:
  role: hub
  name: oracle-hub

models:
  local:
    - name: gpt-5-distill-qwen3-4b
      max_context: 8192
      quantization: Q4_K_M
    - name: gemini3.5-code-reasoner-2b
      max_context: 8192
      quantization: Q4_K_M

edges:
  allowed_tokens: []   # i token vivono in auth.yaml (age), non qui

providers:
  fallback_chain: [local, edge, google, groq, nvidia, cerebras, openrouter, kimi]

compression:
  enabled: true
  port: 9090
  input_reduction: 0.50
  context_dedup: 0.60
  output_quenching: 0.75
  semantic_cache_threshold: 0.92
```

### Edge — `~/.config/tramamind/config.yaml`

```yaml
node:
  role: edge
  name: pc-casa
  hub_url: http://100.x.y.z:20128   # IP Tailscale dell'hub
  # token: in auth.yaml (age), mai in chiaro qui

models:
  served: [gemopus-26b, qwopus-27b]

ollama:
  base_url: http://localhost:11434
  keep_alive: 30m
```

---

## 7. Deploy

| Requisito | Hub (Oracle) | Edge (PC) |
|-----------|-------------|-----------|
| OS | Ubuntu 24.04 ARM64 | Linux/macOS/Windows |
| RAM | 12 GB | 16+ GB |
| Docker | 24+ | 24+ |
| Python | 3.10+ | 3.10+ |
| Rete | Tailscale | Tailscale |

```bash
# Hub
curl -fsSL https://raw.githubusercontent.com/bitfarmy/tramamind/main/scripts/oracle-setup.sh | bash
pip install -e ~/tramamind && tramamind keys setup

# Edge
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemopus-26b-a4b && ollama pull qwopus-27b-v3
pip install -e . && tramamind keys setup
```

---

## 8. Roadmap

| Fase | Stato | Descrizione |
|------|-------|-------------|
| 1 | ✅ Fatto | Architettura, limiti Oracle, providers.yaml, integrazione OpenClaw |
| 2 | ✅ Fatto | `router/config.py` + `router/keystore.py` + CLI `tramamind keys` (testata) |
| 3 | 🔄 Prossima | `topology/hub.py`, `topology/edge.py`, endpoint registrazione |
| 4 | ⏳ | `deploy/docker-compose.hub.yml` / `.edge.yml`, install-hub/edge.sh |
| 5 | ⏳ | Desktop client remoto con indicatori di provenienza |
| 6 | ⏳ | Benchmark latenza/costo hub vs edge vs cloud |

Ogni fase entra nel repo solo quando installabile e testata (regola 5).

---

## Riferimenti

- [Oracle Always Free](https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [vLLM](https://docs.vllm.ai/) · [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) · [keyring](https://pypi.org/project/keyring/) · [age](https://age-encryption.org/)
