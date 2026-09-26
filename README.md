# TramaMind

**IA personale multi-modello** — modelli locali (Ollama), API gratuite e Kimi dietro un unico endpoint, con routing intelligente, compressione token e cache semantica.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/bitfarmy/tramamind/actions/workflows/ci.yml/badge.svg)](https://github.com/bitfarmy/tramamind/actions/workflows/ci.yml)

TramaMind orchestra più fonti di intelligenza dietro un unico endpoint OpenAI-compatibile. Il router ([OmniRoute](https://github.com/diegosouzapw/OmniRoute), MIT) sceglie il provider migliore per ogni richiesta, fa failover automatico quando una quota finisce, comprime i prompt e risponde dalla cache quando possibile. I modelli locali hanno la priorità: privacy totale, zero costi.

> ⚠️ **Uso personale.** Mai rivendita, mai automazione massiva. Vedi [docs/legal.md](docs/legal.md).

---

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│ L5  INTERFACCIA — oggi: CLI (scripts/chat.sh)               │
│     domani: desktop (fork di Berd) con pannello VRAM,       │
│     toggle compressione, selettore modalità, provenienza    │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ L4  ROUTER — OmniRoute (:20128, API OpenAI-compatibile)     │
│     19 strategie di routing · fallback a catena ·           │
│     circuit breaker · quota tracking · dashboard web        │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ L2  COMPRESSIONE — integrata in OmniRoute                   │
│     pipeline a 12 motori (RTK, Caveman, …) 15–95% token     │
│     cache semantica a due livelli                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌───────────────┬─────────────────────────┬───────────────────┐
│ L3A DIRETTO   │ L3B API GRATUITE        │ L3C MODELLI       │
│ Claude Pro    │ Google · Groq · NVIDIA  │ LOCALI su Ollama  │
│ (MAI proxy)   │ Cerebras · OpenRouter   │ (priorità 1)      │
│ Kimi via API  │                         │                   │
└───────────────┴─────────────────────────┴───────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ L1  RUNTIME — Ollama (primario) · LM Studio · llama.cpp ·   │
│     vLLM                                                    │
└─────────────────────────────────────────────────────────────┘
```

Dettagli in [docs/architecture.md](docs/architecture.md).

## Struttura del repository

```
tramamind/
├── README.md
├── LICENSE                  # MIT
├── PROMPT-PROGETTO.md       # istruzioni operative per l'assistente AI
├── .env.example             # template configurazione (copia in .env)
├── docs/
│   ├── architecture.md      # i 5 livelli in dettaglio
│   ├── setup.md             # installazione e configurazione
│   ├── local-models.md      # catalogo modelli locali verificati
│   ├── compression.md       # compressione e cache di OmniRoute
│   └── legal.md             # note legali e ToS
├── desktop/                 # fork di Berd (fase futura)
├── scripts/
│   ├── install.sh           # setup iniziale
│   ├── start-all.sh         # avvia Ollama + OmniRoute
│   ├── stop-all.sh          # ferma i processi avviati da start-all
│   ├── chat.sh              # chat CLI con provenienza risposta
│   ├── stats.sh             # consumi, cache hit rate, risparmio
│   └── doctor.sh            # diagnostica completa dello stack
├── benchmarks/
│   ├── benchmark.sh         # misure su prompt fissi (2 giri: cache)
│   └── prompts.txt          # prompt di test rappresentativi
└── data/                    # log, PID, risultati (gitignored)
```

## Quickstart

**Requisiti:** Node 20+, Python 3.10+, Ollama, 16 GB RAM, 50 GB SSD.

```bash
git clone https://github.com/bitfarmy/tramamind.git
cd tramamind
./scripts/install.sh          # dipendenze + crea .env
$EDITOR .env                  # inserisci le tue chiavi API
./scripts/doctor.sh           # verifica che tutto sia a posto
./scripts/start-all.sh        # avvia Ollama + OmniRoute
./scripts/chat.sh             # chatta!
```

Dashboard OmniRoute: `http://localhost:20128` — API: `http://localhost:20128/v1`.

## Script

| Script | Cosa fa |
|---|---|
| `chat.sh` | Chat CLI: mostra **provider, latenza e token** dopo ogni risposta |
| `stats.sh` | Consumi per provider, **cache hit rate**, stima risparmio |
| `doctor.sh` | **Diagnostica completa**: dipendenze, servizi, chiavi, hardware |
| `install.sh` | Setup iniziale (dipendenze, `.env`, modelli con `--pull-models`) |
| `start-all.sh` / `stop-all.sh` | Avvio/arresto dello stack |
| `benchmarks/benchmark.sh` | Misure su prompt fissi, due giri per la cache |

## Regole d'oro

1. **Chiavi API solo in `.env`** (gitignored), mai in chiaro nel codice.
2. **Claude Pro SOLO diretto** (Claude Code CLI / claude.ai), MAI proxyato — rischio ban.
3. **Modelli locali = priorità 1**: privacy totale, zero costi.
4. **Niente numeri non misurati**: il risparmio si misura con `benchmarks/benchmark.sh`, non si stima a priori.
5. Uso personale, mai rivendita né automazione massiva.

## Roadmap

- [x] Commit zero: struttura repo + CI
- [x] Quick win: provenienza in CLI (`chat.sh`)
- [x] Quick win: statistiche (`stats.sh`)
- [x] Quick win: diagnostica (`doctor.sh`)
- [ ] Alias per task
- [ ] Auto-detect hardware
- [ ] Avvio automatico
- [ ] Benchmark A/B sulle strategie di routing
- [ ] Documentazione inglese
- [ ] Desktop (fork di Berd)

## Crediti

- [OmniRoute](https://github.com/diegosouzapw/OmniRoute) — router/gateway (MIT)
- [Ollama](https://ollama.com) — runtime modelli locali
- Le famiglie di modelli in [docs/local-models.md](docs/local-models.md) restano dei rispettivi titolari

## Licenza

[MIT](LICENSE) © 2026 bitfarmy
