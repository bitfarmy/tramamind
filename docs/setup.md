# Setup

## Requisiti

| Requisito | Minimo | Verifica |
|---|---|---|
| Node.js | 20+ | `node --version` |
| Python | 3.10+ | `python3 --version` |
| Ollama | latest | `ollama --version` |
| RAM | 16 GB | `free -h` |
| SSD | 50 GB liberi | `df -h` |
| jq | qualsiasi | richiesto da `benchmarks/benchmark.sh` |

## Installazione

```bash
git clone https://github.com/bitfarmy/tramamind.git
cd tramamind
./scripts/install.sh
```

`install.sh`:

1. Verifica le dipendenze (incluso OmniRoute: se manca, propone
   `npm install -g omniroute`).
2. Crea `.env` da `.env.example` (se assente).
3. Crea `data/` (log, PID, risultati benchmark).
4. Con `--pull-models` scarica una selezione di modelli locali su Ollama.

## Configurazione

Modifica `.env` nella radice:

```bash
# Provider a pagamento/basso costo
KIMI_API_KEY=sk-...

# Provider gratuiti (lascia vuoti quelli che non usi)
GOOGLE_API_KEY=AIza...
GROQ_API_KEY=gsk_...
NVIDIA_API_KEY=nvapi-...
CEREBRAS_API_KEY=csk-...
OPENROUTER_API_KEY=sk-or-...

# Override opzionali per chat.sh
#TRAMAMIND_ENDPOINT=http://localhost:20128/v1/chat/completions
#TRAMAMIND_MODEL=auto
#TRAMAMIND_TIMEOUT=120
```

> 🔐 `.env` è nel `.gitignore`. Non committarlo mai.

Le chiavi vanno inserite **anche nella dashboard di OmniRoute**
(`http://localhost:20128` → Providers), che è il punto dove il router le usa
davvero. Il `.env` serve agli script TramaMind e come promemoria sicuro.

## OmniRoute: configurazione consigliata

Dalla dashboard:

1. **Providers** → connetti Ollama (locale) e i provider cloud con le tue chiavi.
2. **Fallback Chains** → catena consigliata:
   `Ollama → Google → Groq → NVIDIA → Cerebras → OpenRouter → Kimi`
3. **Compression** → attiva la pipeline (RTK + Caveman per iniziare).
4. **Semantic Cache** → attiva.
5. **Endpoints** → copia la API key da usare nei client.

## Avvio

```bash
./scripts/start-all.sh   # Ollama + OmniRoute (PID in data/)
./scripts/doctor.sh      # verifica lo stato di tutto lo stack
./scripts/chat.sh        # prima chat
```

## Verifica rapida

```bash
./scripts/chat.sh "Scrivi un haiku sulla privacy"
# → risposta + riga di provenienza:
#   ⚡ provider=ollama/qwen3:8b · 842ms · 312 token (in 45 / out 267)
```

## Alias per task

Scorciatoie per scegliere il modello in base al task:

```bash
./scripts/chat.sh --code "refactora questa funzione"   # qwen2.5-coder:7b
./scripts/chat.sh --think "risolvi questo problema"   # deepseek-r1:8b
./scripts/chat.sh --fast "traduci questo"             # gemma3:4b
./scripts/chat.sh --write "scrivi un post"            # qwen3:8b
```

Senza alias il modello è `auto`: decide il router. Nel REPL: `/alias`
mostra la mappa con il modello attivo, `/use NOME` cambia alias al volo.
I modelli associati si personalizzano in `.env` (`ALIAS_CODE=`, …).

## Problemi comuni

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| `connection refused :11434` | Ollama non avviato | `ollama serve` o `./scripts/start-all.sh` |
| `connection refused :20128` | OmniRoute non avviato | `omniroute` o `./scripts/start-all.sh` |
| `401 Unauthorized` | API key client errata | Dashboard → Endpoints → copia la chiave |
| Failover continui | Provider in rate limit | Normale: il router scala la catena |
| OOM sui modelli locali | VRAM/RAM insufficiente | Modello più piccolo: [local-models.md](local-models.md) |
