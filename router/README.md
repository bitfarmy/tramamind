# Router (L4) — OmniRoute

OmniRoute è il gateway/router di TramaMind. Documentazione ufficiale:
https://github.com/diegosouzapw/OmniRoute

## Fatti chiave

| Voce | Valore |
|---|---|
| Porta | **20128** (dashboard + API sullo stesso processo) |
| API OpenAI-compatible | `http://localhost:20128/v1` |
| Install npm | `npm install -g omniroute && omniroute` |
| Docker | `diegosouzapw/omniroute:latest` (multi-arch AMD64/ARM64) |
| Node richiesto | `>=22.22.2 <23` oppure `>=24 <27` |
| Smart routing | modello `auto` = routing zero-config |
| API key per i client | Dashboard → Endpoints |

## Perché la porta 20128 e non 8080

Lo schema originale TramaMind indicava 8080: era un placeholder. Il default
upstream è 20128; cambiarlo è possibile (`omniroute --port 8080` / `-p 8080:20128`)
ma non consigliato: la documentazione, il CLI (`omniroute connect
http://localhost:20128`) e le guide upstream assumono il default.

## Configurazione provider

1. Avvia OmniRoute → dashboard http://localhost:20128
2. **Providers** → collega Google AI Studio, Groq, NVIDIA NIM, Cerebras,
   OpenRouter, Kimi (le chiavi arrivano dal `.env` o si inseriscono in dashboard)
3. **Endpoints** → genera la API key che i client (OpenHands, chat.sh)
   useranno verso il router
4. I modelli locali appaiono automaticamente via Ollama
   (`http://localhost:11434/v1`) una volta scaricati con `ollama pull`

## Memoria: fondamentale con gli agenti

Il default `OMNIROUTE_MEMORY_MB=1024` basta per la chat. Con agenti di coding
(contesti lunghi e sovrapposti su `/v1/responses`) il processo va in
`FATAL ERROR` di heap V8. TramaMind imposta:

- `OMNIROUTE_MEMORY_MB=8192` (heap)
- container ≥ 10 GB RAM (`OMNIROUTE_CONTAINER_MEM=10g`, solo compose)

## Compressione (L2)

Integrata in OmniRoute: pipeline a 12 motori (RTK, Caveman, LLMLingua-2, …)
più cache semantica a due livelli. Si attiva da Dashboard → Compression.
Nessun proxy separato. Dettagli: [../docs/compression.md](../docs/compression.md)

## Regola L3A

Claude Pro **non** si configura qui: solo Claude Code CLI / claude.ai con
accesso diretto. Proxyarlo violerebbe i termini (rischio ban).
