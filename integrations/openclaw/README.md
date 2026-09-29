# TramaMind × OpenClaw — Gateway omnicanale (L5b)

OpenClaw espone TramaMind su Telegram (e opzionalmente WhatsApp/Discord) senza toccare lo stack esistente: punta a **OmniRoute** come provider OpenAI-compatible, quindi compressione (Entropy Gate), routing, failover e distillati restano tutti attivi.

```
Tu (Telegram) → OpenClaw :18789 → OmniRoute :8080 → Entropy Gate :9090 → provider
```

## Prerequisiti

- Stack TramaMind avviato: OmniRoute su `localhost:8080` (e Ollama su `11434` per i distillati)
- Docker + Docker Compose
- Un bot Telegram: parla con **@BotFather** → `/newbot` → copia il token

## Setup (5 minuti)

```bash
cd integrations/openclaw

# 1. Configura i segreti
cp .env.example .env
#    → incolla TELEGRAM_BOT_TOKEN
#    → genera OPENCLAW_GATEWAY_TOKEN con: openssl rand -hex 32

# 2. Avvia
docker compose up -d

# 3. Primo avvio: attendi 3-7 min (compilazione WASM), poi verifica
docker logs tramamind-openclaw --follow
#    atteso: "Gateway listening on port 18789"
```

## Pairing Telegram

1. Scrivi qualsiasi cosa al tuo bot su Telegram → ricevi un **codice di pairing**
2. Approvalo:
   ```bash
   docker compose exec openclaw-gateway node dist/index.js pairing approve telegram <CODICE>
   ```
3. Scrivi di nuovo al bot: ti risponde TramaMind (via OmniRoute).

**Indurimento consigliato:** dopo il pairing, recupera il tuo chat ID e decommenta
`allowFrom: ["<tuo-chat-id>"]` in `openclaw.json`, poi `docker compose restart`.

## Uso

| Comando in chat | Effetto |
|---|---|
| messaggio qualsiasi | risposta via `tramamind/auto` (router decide) |
| `/model locale` | forza i distillati Ollama (privacy totale, costo zero) |
| `/model cloud` | forza le API gratuite |
| `/model auto` | torna al routing automatico |
| `/new` o `/reset` | nuova sessione |

L'**heartbeat** (ogni 30 min) gira solo su `tramamind/local`: briefing e reminder a costo zero. Modifica `agents.defaults.heartbeat` in `openclaw.json` per cambiare frequenza o disattivarlo.

## Dashboard (opzionale)

```bash
docker compose exec openclaw-gateway node dist/index.js dashboard --no-open
# apri l'URL stampato (http://127.0.0.1:18789/?token=...)
```

## Note e limiti

- **Claude non passa di qui.** Dopo il cambio pricing Anthropic (aprile 2026), Claude su harness di terze parti richiede billing pay-as-you-go. Claude Pro resta solo su Claude Code CLI diretto (regola L3A).
- **Niente fallback silenziosi:** `fallbacks: []` è voluto — se OmniRoute è giù, l'errore deve essere visibile, non deviato su provider a pagamento.
- **PC spento = gateway fermo.** Per il 24/7 serve il nodo always-on (vedi `docs/setup.md`).
- I nomi modello `auto` / `local` / `cloud` devono corrispondere al registry di OmniRoute: se OmniRoute espone nomi diversi, allinea `models.providers.tramamind.models[]`.
- RAM minima container: **2 GB** (sotto va in OOM all'avvio).

## Troubleshooting

| Sintomo | Causa probabile | Fix |
|---|---|---|
| Container esce subito (exit 137) | RAM < 2 GB | alza `mem_limit` |
| Il bot non risponde | OmniRoute non raggiungibile dal container | verifica `extra_hosts` e che OmniRoute ascolti su `0.0.0.0` o sia sull'host |
| Nessun pairing code | token Telegram errato | rigenera da @BotFather, aggiorna `.env` |
| Risposte lente al primo messaggio | distillato in caricamento su Ollama | normale cold start, poi va in cache |
