# Architettura

TramaMind è organizzato in **5 livelli logici**, dalla presentazione al runtime.
Due componenti fanno il grosso del lavoro: **OmniRoute** (router/gateway) e
**Ollama** (runtime locale). Tutto il resto è configurazione e script.

> ⚠️ Questo documento descrive lo stack **reale**. Niente componenti
> aspirazionali: se qualcosa non esiste come pacchetto installabile, qui non
> c'è.

## L5 — Interfaccia

**Oggi:** la CLI (`scripts/chat.sh`), un REPL da terminale che mostra
provenienza, latenza e token per ogni risposta.

**Domani (fase 3):** fork di Berd con:

- pannello VRAM dei modelli locali caricati,
- toggle compressione ON/OFF,
- selettore modalità `Locale` / `Cloud` / `Auto`,
- indicatore di provenienza per ogni risposta.

Entrambe parlano con OmniRoute via API OpenAI-compatibile: nessuna logica
di routing nell'interfaccia.

## L4 — Router: OmniRoute (`:20128`)

Installazione: `npm install -g omniroute`. Dashboard e API sullo stesso
endpoint (`http://localhost:20128`, API sotto `/v1`).

Cosa fa per noi (già incluso, **non reimplementare**):

- **19 strategie di routing**: `priority`, `weighted`, `round-robin`,
  `cost-optimized`, `context-optimized`, `cache-optimized`, `fusion`,
  `pipeline`, `auto` (bandit adattivo), …
- **Fallback a catena** con circuit breaker e cooldown esponenziale su
  `429`/`5xx` (rispetta `Retry-After`).
- **Quota tracking** per provider e chiave, con lock giornaliero a esaurimento.
- **Cache semantica** a due livelli (signature + semantica).
- **Compressione** (vedi L2).
- **Dashboard**: latenze p50/p95/p99, stato provider, costi, log.

La catena di failover si configura dalla dashboard (Fallback Chains). Quella
consigliata per TramaMind:

```
Ollama (locale) → Google → Groq → NVIDIA → Cerebras → OpenRouter → Kimi
```

## L3 — Provider

### L3A — Accesso diretto (mai proxyato)

- **Claude Pro**: SOLO via Claude Code CLI o claude.ai. **MAI** attraverso
  OmniRoute o qualsiasi proxy: viola i ToS e rischia il ban.
- **Kimi**: via API ufficiale (`platform.moonshot.ai`), supportata da
  OmniRoute come provider first-class.

### L3B — API gratuite

| Provider | Console | Note |
|---|---|---|
| Google AI Studio | aistudio.google.com | Tier gratuito generoso |
| Groq | console.groq.com | Latenza bassissima |
| NVIDIA NIM | build.nvidia.com | Buona varietà modelli |
| Cerebras | cloud.cerebras.ai | Inferenza ultra-veloce |
| OpenRouter | openrouter.ai | Aggregatore, modelli free |

OmniRoute supporta 300+ provider e 90+ tier gratuiti: questi cinque sono la
selezione di TramaMind, non il limite.

### L3C — Modelli locali (priorità 1)

Girano su Ollama (`localhost:11434/v1`) e OmniRoute li vede come provider
locali. Privacy totale, zero costi, funzionano offline. Catalogo verificato
in [local-models.md](local-models.md): Qwen2.5-Coder / Qwen3 (codice),
Gemma 3 (generale), DeepSeek-R1 Distill (ragionamento).

## L2 — Compressione (integrata in OmniRoute)

**Non è un processo separato.** OmniRoute include una pipeline di
compressione a 12 motori (Session-Dedup, RTK, Caveman, LLMLingua-2, …) che
riduce i token idonei del **15–95%** a seconda del carico, più la cache
semantica che azzera il costo delle richieste ripetute.

Aspettative oneste: su traffico misto reale il risparmio tipico è **20–50%**;
oltre l'85% solo con cache hit alti. Si misura con
`benchmarks/benchmark.sh`, non si stima. Dettagli in
[compression.md](compression.md).

## L1 — Runtime

| Runtime | Ruolo |
|---|---|
| **Ollama** | Primario — serve i modelli locali |
| LM Studio | Alternativo / debug |
| llama.cpp | Fallback minimale |
| vLLM | Throughput elevato (multi-batch) |

Tutti esposti a OmniRoute come provider locali.

## Flusso di una richiesta

```
chat.sh ──► OmniRoute :20128 ──► (cache hit? → risposta immediata)
                │
                ▼
        strategia di routing + compressione prompt
                │
                ▼
        provider scelto (locale prima, poi cloud)
                │  errore 429/5xx? → cooldown + prossimo della catena
                ▼
        risposta ──► chat.sh (testo + provenienza: provider, ms, token)
```

Ogni richiesta è loggata in `data/requests.jsonl` e aggregata da
`scripts/stats.sh`.
