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
│                  Ampere A1 — 4 OCPU / 24 GB                 │
│  ┌──────────────────────────┐  ┌─────────────────────────┐  │
│  │  OmniRoute :20128        │  │ Ollama :11434 (GGUF)    │  │
│  │  L2 integrato:           │  │ 9B primario · 4B · 2B   │  │
│  │  compressione + cache    │  │ ctx 8k, keep-alive      │  │
│  └──────────────────────────┘  └─────────────────────────┘  │
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

> **Nota L2**: la compressione è **integrata in OmniRoute** (pipeline a 12
> motori + cache semantica a due livelli, si attiva da Dashboard →
> Compression). Nessun proxy separato, nessuna porta extra.
> Dettagli: [compression.md](compression.md)

### Flusso richiesta

1. Il client (desktop, OpenClaw/Telegram, CLI) invia la richiesta a OmniRoute sull'hub
2. OmniRoute classifica il task e verifica i modelli disponibili
3. **Task semplice** → distillati locali su Oracle via Ollama (9B/4B/2B, costo 0)
4. **Task complesso + PC online** → instrada all'edge (Gemopus 26B / Qwopus 27B)
5. **PC offline** → fallback API cloud gratuite
6. Risposta → compressione/cache L2 (interna a OmniRoute) → client, con provenienza

---

## 2. Limiti Oracle Free Tier

| Risorsa | Limite | Utilizzo TramaMind |
|---------|--------|-------------------|
| Ampere A1 | fino a 4 OCPU / 24 GB RAM | Ollama GGUF (9B+4B+2B) + servizi |
| Storage | 200 GB totali | 100 GB boot volume: modelli + log + cache |
| Egress | 10 TB/mese | Mai raggiungibile per uso personale |
| IP pubblico | 1 incluso | Statico, assegnato alla VM |

> Dal 15 giugno 2026 gli account **free-only** hanno 2 OCPU/12 GB; le
> tenancy **PAYG** mantengono 4 OCPU/24 GB gratuiti (verificato sul nostro
> account il 2026-09-29, banner in console: 3.000 OCPU-ore + 18.000 GB-ore).
> Budget alert a 1 $ obbligatorio. Dettagli: [oracle-free-tier.md](oracle-free-tier.md)

---

## 3. Stack tecnico

### Hub (Oracle) — budget RAM 24 GB (account PAYG)

| Componente | Tecnologia | RAM |
|------------|-----------|-----|
| Sistema + Docker | Ubuntu 24.04 ARM64 | ~2 GB |
| Ollama + Qwen3.5-9B-Claude-Opus-Distill-v2 (GGUF Q4_K_M) | ctx 8k | ~7 GB |
| Ollama + GPT-5-Distill-Qwen3-4B e Gemini3.5-Code-Reasoner-2B | co-caricabili, keep-alive | ~5 GB |
| OmniRoute (L2 incluso) | :20128 | ~1.5 GB |
| Buffer | — | ~9 GB |

Modelli hub: **Qwen3.5-9B-Claude-Opus-Distill-v2** (primario),
**GPT-5-Distill-Qwen3-4B** (bilanciato), **Gemini3.5-Code-Reasoner-2B**
(fast lane/heartbeat). Esclusi: 26B/27B (solo edge).
Su account free-only (12 GB): niente 9B, budget come da
[oracle-free-tier.md](oracle-free-tier.md).

**Runtime hub: Ollama con GGUF.** vLLM su ARM64 è accantonato: immagine
ufficiale x86-only, e i pesi bf16 occuperebbero il doppio dei GGUF Q4
girando più lenti su CPU ARM (vedi decisione 10 in hub-edge-topology.md).

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
In quel caso aprire solo 80/443 nella Security List OCI — mai 20128/11434/18789.

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
nessun elenco hardcoded.

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
    - name: qwen3.5-9b-claude-opus-distill-v2   # primario (solo su hub da 24 GB)
      max_context: 8192
      quantization: Q4_K_M
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

# L2: nessuna configurazione di porta — si attiva da OmniRoute Dashboard →
# Compression (pipeline RTK/Caveman + cache semantica). Vedi compression.md
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
| RAM | 24 GB (12 su free-only) | 16+ GB |
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
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) · [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) · [keyring](https://pypi.org/project/keyring/) · [age](https://age-encryption.org/)
