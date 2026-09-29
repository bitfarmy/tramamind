# 🧵 TramaMind

IA personale multi-modello: modelli locali (Ollama), API gratuite (Google,
Groq, NVIDIA, Cerebras, OpenRouter) e Kimi via API, orchestrati dal router
**OmniRoute** con compressione token e cache semantica integrate.
Claude Pro si usa solo in modo diretto, mai proxyato.

**Licenza: MIT** — uso personale, mai rivendita né automazione massiva.

## Architettura

```
┌─────────────────────────────────────────────────────────┐
│ L-APP  OpenHands (agente di coding, opzionale)          │
│        → chiama l'API di OmniRoute come un client       │
├─────────────────────────────────────────────────────────┤
│ L5  Interfaccia: CLI (scripts/chat.sh)                  │
│     fase futura: app desktop (fork di Berd)             │
│ L5b Gateway omnicanale: OpenClaw (Telegram, opz.        │
│     WhatsApp/Discord) → OmniRoute come provider         │
├─────────────────────────────────────────────────────────┤
│ L4  Router: OmniRoute :20128                            │
│     smart routing (modello "auto") · failover 429/5xx   │
│     catena: Ollama → Google → Groq → NVIDIA →           │
│             Cerebras → OpenRouter → Kimi                │
│     L2 integrato: compressione (RTK/Caveman/…) +        │
│     cache semantica — nessun proxy separato             │
├─────────────────────────────────────────────────────────┤
│ L3A Claude Pro SOLO diretto (Claude Code CLI/claude.ai) │
│ L3B API gratuite: Google, Groq, NVIDIA, Cerebras,       │
│     OpenRouter · Kimi via API                           │
│ L3C Modelli locali su Ollama :11434 (priorità 1:        │
│     privacy totale, zero costi)                         │
├─────────────────────────────────────────────────────────┤
│ L1  Runtime: Ollama (primario) · LM Studio · llama.cpp  │
│     vLLM sul nodo Oracle (CPU backend)                  │
└─────────────────────────────────────────────────────────┘
```

Dettagli: [docs/architecture.md](docs/architecture.md)

## Quick start

```bash
git clone https://github.com/bitfarmy/tramamind.git
cd tramamind
./scripts/install.sh --pull-models --with-openhands
# compila .env, poi inserisci le chiavi in OmniRoute (Dashboard → Providers)
./scripts/start-all.sh
./scripts/chat.sh "Scrivi un haiku sulla privacy"
```

Guida completa: [docs/setup.md](docs/setup.md)

### Alternativa Docker Compose

```bash
cp .env.example .env   # compila le chiavi
docker compose up -d
```

## Nodo always-on 24/7 (Oracle Cloud Always Free)

Per usare TramaMind anche a PC spento: una VM ARM Oracle Always Free
(**2 OCPU / 12 GB**, limiti aggiornati a giugno 2026) ospita lo stack
completo in versione leggera:

```
Oracle A1 (2 OCPU / 12 GB)
├── Sistema + Docker        ~2 GB
├── vLLM (Qwen3-4B)         ~4 GB   (weights + KV cache 8k)
├── Entropy Gate            ~1 GB
├── OmniRoute               ~0.5 GB
└── Buffer                  ~4.5 GB
```

Modelli sul nodo: **GPT-5-Distill-Qwen3-4B** (primario) e
**Gemini3.5-Code-Reasoner-2B** (task veloci/heartbeat). Esclusi: Qwen3.5-9B
(troppo rischioso su 12 GB) e i 26B/27B (solo PC locale, raggiungibili via
Tailscale quando il PC è acceso). Accesso via Tailscale, zero porte esposte,
costo 0 €/mese.

```bash
# sulla VM Oracle (Ubuntu 24.04 ARM):
curl -fsSL https://raw.githubusercontent.com/bitfarmy/tramamind/main/scripts/oracle-setup.sh | bash
```

Guida completa: [docs/oracle-free-tier.md](docs/oracle-free-tier.md)

## Script

| Script | Cosa fa |
|---|---|
| `scripts/install.sh` | Verifica dipendenze, crea `.env` e `data/`; `--pull-models`, `--with-openhands` |
| `scripts/start-all.sh` | Avvia Ollama + OmniRoute (+ OpenHands, `--no-openhands` per saltarlo) |
| `scripts/stop-all.sh` | Ferma solo ciò che ha avviato start-all |
| `scripts/chat.sh` | REPL CLI con provenienza, latenza e token per risposta |
| `scripts/doctor.sh` | Diagnostica completa dello stack |
| `scripts/stats.sh` | Statistiche d'uso dai log |
| `scripts/start-openclaw.sh` | Avvia il gateway OpenClaw (dopo aver verificato OmniRoute) |
| `scripts/oracle-setup.sh` | Provisioning VM Oracle Always Free (Docker, vLLM, UFW, swap) |
| `benchmarks/benchmark.sh` | Misura routing + compressione + cache sui tuoi prompt |

## OpenHands (agente di coding autonomo)

OpenHands (MIT, self-hosted) è integrato come **livello applicativo**: punta
all'endpoint OpenAI-compatible di OmniRoute e ogni sua chiamata eredita
routing per capability, failover e compressione — un task agentico genera
50–200 chiamate LLM, ed è proprio il workload dove cache semantica e
fallback fanno la differenza. UI su http://localhost:3000.

Guida: [docs/openhands-integration.md](docs/openhands-integration.md)

## OpenClaw (gateway Telegram / WhatsApp / Discord)

OpenClaw (MIT) è integrato come **livello L5b**: un gateway che espone
TramaMind su Telegram (e opzionalmente WhatsApp/Discord) puntando a
OmniRoute come provider OpenAI-compatible. Routing, failover, compressione
e cache semantica restano tutti attivi — da Telegram puoi anche forzare la
corsia con `/model locale` (solo modelli locali) o `/model cloud` (solo API
gratuite). Gira in Docker hardened (bind su 127.0.0.1, read-only,
sandbox per i tool); heartbeat periodico solo su modelli locali, costo zero.

```bash
cd integrations/openclaw
cp .env.example .env   # token bot Telegram da @BotFather
docker compose up -d
```

Guida: [integrations/openclaw/README.md](integrations/openclaw/README.md)

Nota: Claude **non** passa da OpenClaw — su harness di terze parti richiede
billing pay-as-you-go (cambio Anthropic, aprile 2026). Claude Pro resta
solo su Claude Code CLI diretto (regola 4).

## Documentazione

| Doc | Contenuto |
|---|---|
| [docs/architecture.md](docs/architecture.md) | I 5 livelli e le scelte di design |
| [docs/setup.md](docs/setup.md) | Installazione, configurazione, problemi comuni |
| [docs/local-models.md](docs/local-models.md) | Scelta dei modelli locali per hardware |
| [docs/compression.md](docs/compression.md) | Pipeline di compressione e cache semantica |
| [docs/openhands-integration.md](docs/openhands-integration.md) | Integrazione agente ↔ router |
| [docs/oracle-free-tier.md](docs/oracle-free-tier.md) | Nodo always-on 24/7 su Oracle Cloud |
| [integrations/openclaw/README.md](integrations/openclaw/README.md) | Gateway omnicanale Telegram/WhatsApp |
| [docs/legal.md](docs/legal.md) | Licenze e termini d'uso |

## Regole inviolabili

1. Chiavi API solo in `.env` (gitignored), mai in chiaro nel codice
2. Uso personale: niente rivendita né automazione massiva
3. Modelli locali = priorità 1 (privacy totale, zero costi)
4. Claude Pro resta fuori dal router — solo accesso diretto
5. Niente componenti aspirazionali: se non è installabile, non è nel repo

## Requisiti

**PC principale:** Node 22.22.2+ (o 24–26) · Python 3.10+ · Ollama · Docker
(per OpenHands e OpenClaw) · 16 GB RAM · 50 GB SSD · jq (per i benchmark)

**Nodo Oracle (opzionale):** account Oracle Cloud · VM.Standard.A1.Flex
2 OCPU / 12 GB (Always Free) · Ubuntu 24.04 ARM64
