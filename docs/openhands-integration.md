# Integrazione OpenHands + OmniRoute

Come far lavorare insieme l'agente di coding autonomo (OpenHands) e il router
(OmniRoute) dentro TramaMind.

---

## 1. Ruoli: non si scelgono, si combinano

| | OmniRoute | OpenHands |
|---|---|---|
| Cosa è | Gateway/router LLM | Agente di coding autonomo |
| Cosa fa | Decide **a quale modello** va ogni chiamata | Esegue **task**: legge file, scrive codice, runna shell in sandbox Docker |
| Licenza | MIT | MIT (self-hosted) |
| Livello TramaMind | L4 | L-APP (applicativo, sopra L5) |
| Alternativa a | LiteLLM, Portkey, Bifrost | Claude Code, Aider, Codex |

OpenHands è model-agnostic e sotto il cofano usa LiteLLM: per puntarlo a un
endpoint OpenAI-compatible bastano tre valori — modello con prefisso
`openai/`, base URL, API key. OmniRoute espone esattamente quell'endpoint
(`http://localhost:20128/v1`).

## 2. Perché la sinergia vale

Un agente autonomo non è una chat: un singolo task di coding produce
**50–200 chiamate LLM** (pianifica → legge file → scrive → esegue → legge
l'errore → riprova…). Senza router:

- puntato al cloud → brucia quota in fretta;
- puntato al solo locale → qualità insufficiente sui task duri;
- un 429 a metà task → task fallito.

Con OpenHands → OmniRoute ogni chiamata eredita:

1. **Smart routing** — con modello `auto` il router manda i passi semplici sui
   modelli locali (costo zero, privacy totale) e scala al cloud gratuito solo
   per il ragionamento duro.
2. **Failover** — 429/5xx su un provider → provider successivo, senza che il
   task agentico fallisca.
3. **Compressione e cache (L2, integrata in OmniRoute)** — gli agenti
   rileggono gli *stessi file* decine di volte: è il workload dove Session-
   Dedup, RTK e la cache semantica rendono di più. Vedi
   [compression.md](compression.md).
4. **Osservabilità unica** — il traffico dell'agente finisce negli stessi
   log/dashboard del resto di TramaMind (`scripts/stats.sh`).

## 3. Flusso

```
┌────────────┐  50–200 chiamate/task  ┌──────────────────┐
│ OpenHands  │ ─────────────────────► │ OmniRoute :20128 │
│  (L-APP)   │ ◄───────────────────── │    (L4 + L2)     │
└────────────┘  risposta+provenienza  └───────┬──────────┘
                                              │ smart routing + failover
                                              │ compressione + cache (integrate)
                              ┌───────────────┴───────────────┐
                     semplice │                               │ difficile
                              ▼                               ▼
                  ┌────────────────────┐          ┌───────────────────────┐
                  │ Locali (L3C)       │          │ API gratuite (L3B)    │
                  │ Ollama :11434      │          │ Google→Groq→NVIDIA→   │
                  │ qwen2.5-coder, ecc │          │ Cerebras→OpenRouter→  │
                  └────────────────────┘          │ Kimi                  │
                                                  └───────────────────────┘
   Claude Pro (L3A): FUORI da questo flusso, solo accesso diretto.
```

## 4. Configurazione

### 4.1 Installazione e avvio

```bash
./scripts/install.sh --with-openhands   # aggiunge le immagini Docker
./scripts/start-all.sh                  # aggiungi --no-openhands per saltarlo
```

### 4.2 Chiave del router

Dashboard OmniRoute (http://localhost:20128) → **Endpoints** → genera la API
key → mettila in `OMNIROUTE_API_KEY` nel `.env`. La usano sia `chat.sh` sia
OpenHands.

### 4.3 Come OpenHands punta al router

Già configurato via env in `start-all.sh` e `docker-compose.yml`:

```
LLM_MODEL=openai/auto                          # prefisso openai/ OBBLIGATORIO
LLM_BASE_URL=http://host.docker.internal:20128/v1   # nativo
#             http://omniroute:20128/v1             # docker compose
LLM_API_KEY=<OMNIROUTE_API_KEY>
LLM_NUM_RETRIES=2                              # failover delegato al router
LLM_TIMEOUT=300
```

Equivalente da UI: OpenHands → Settings → LLM → Advanced → provider
"OpenAI Compatible", Custom Model `openai/auto`, Base URL come sopra.
Per installazioni native/CLI c'è anche [../openhands/config.toml](../openhands/config.toml).

Varianti di `OPENHANDS_MODEL`:

| Valore | Effetto |
|---|---|
| `openai/auto` | smart routing OmniRoute (consigliato) |
| `openai/qwen2.5-coder:7b` | forza il locale: privacy totale, task leggeri |
| `openai/qwen3:8b` | locale generalista con ragionamento |

### 4.4 Verifica

In OpenHands, nuova conversazione: `Say hello in French.` → risposta attesa
`Bonjour` (la prima può richiedere 30–60 s: avvio del sandbox).
Nella dashboard OmniRoute vedi le chiamate con provider e token.

## 5. Trappole note (e come sono disinnescate)

| Problema | Causa | Mitigazione |
|---|---|---|
| **Doppio retry** | OpenHands (LiteLLM) e OmniRoute ritentano entrambi → backoff sommati | `LLM_NUM_RETRIES=2`: il failover vive solo nel router |
| **OmniRoute FATAL ERROR** | heap V8 default 1 GB insufficiente per contesti lunghi agentici | `OMNIROUTE_MEMORY_MB=8192`; in compose container ≥10 GB |
| **Errori 400 criptici** | modello senza prefisso `openai/` | sempre `openai/<modello>` |
| **Agente muto** | alcuni backend non gradiscono lo streaming | `disable_streaming = true` nel `[llm]` di config.toml |
| **localhost dal container** | in Docker localhost ≠ host | nativo: `host.docker.internal`; compose: rete interna |
| **Timeout** | default troppo bassi per step da minuti | `LLM_TIMEOUT=300` |

## 6. Limiti onesti

- **Interfacce separate**: OpenHands ha la sua UI (:3000); la CLI TramaMind
  resta per la chat. La futura app desktop (fork Berd) potrà mostrare le
  metriche del traffico agentico, non incorporare la UI dell'agente.
- **Risorse condivise**: OpenHands + modelli locali competono per RAM/VRAM;
  su 16 GB conviene tenere caricati modelli piccoli (`qwen2.5-coder:3b`,
  `gemma3:4b`) durante le sessioni agentiche.
- **"Gratuito" ha un tetto**: i tier free hanno rate limit; workload agentici
  intensivi saturano la quota. Il failover copre, ma la qualità degrada verso
  i modelli locali — è il comportamento voluto (priorità 1: locali).
- **Draft editor**: i profili LLM secondari (es. un modello piccolo per le
  bozze di edit) funzionano solo in dev mode, non con `docker run`.

## 7. Note di stack

- Compressione: **integrata in OmniRoute**, nessun processo separato — si
  attiva da Dashboard → Compression. Misura l'impatto con
  `benchmarks/benchmark.sh` (giro 2 = cache hit).
- Requisito Node di OmniRoute: **>= 22.22.2 oppure 24–26** (più stretto del
  "Node 20+" di [setup.md](setup.md): prevale questo per OmniRoute).
