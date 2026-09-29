# Topologia hub/edge — design

Evoluzione di TramaMind da nodo singolo a sistema distribuito:
**hub** sempre attivo su Oracle (modelli leggeri + routing + API gratuite),
**edge** sul PC di casa (modelli pesanti, si registra sull'hub quando acceso).

> Stato: **design approvato, implementazione pianificata**.
> Regola 5: finché un componente non è installabile, nel repo vive solo
> come documento di design + configurazione dichiarativa.

## Ruoli

| Ruolo | Dove | Serve | Requisiti |
|---|---|---|---|
| `standalone` | PC o VM singola | tutto lo stack (default attuale) | 16 GB RAM |
| `hub` | Oracle A1.Flex (2 OCPU/12 GB) | vLLM 4B+2B, OmniRoute, Entropy Gate, endpoint registrazione edge | Always Free |
| `edge` | PC casa/ufficio | Ollama con Gemopus 26B / Qwopus 27B, registrazione su hub | 16+ GB RAM |

### Perché non il 9B sull'hub

La prima bozza prevedeva Qwen3.5-9B su Oracle: scartata. Con 12 GB totali,
6 GB di pesi + KV cache lasciano ~4–5 GB per sistema, OmniRoute, Entropy
Gate e OpenClaw — troppo rischioso. L'hub serve:

- **GPT-5-Distill-Qwen3-4B** (~3 GB) — primario
- **Gemini3.5-Code-Reasoner-2B** (~1.5 GB) — fast lane, heartbeat

## Rete e sicurezza

Decisione: **Tailscale-only, nessuna porta pubblica** (vedi
[oracle-free-tier.md](oracle-free-tier.md)). Conseguenze:

- Niente dominio pubblico né reverse proxy TLS: hub ed edge si parlano
  sull'overlay Tailscale (già cifrato WireGuard)
- L'edge si registra su `http://<ip-tailscale-hub>:20128/api/v1/edges/register`
- Il **token edge** resta come autenticazione applicativa (difesa in
  profondità): l'hub verifica il token prima di instradare qualsiasi richiesta
- I token vivono in `~/.config/tramamind/auth.yaml` cifrato con **age**

## Gestione chiavi API — risoluzione a cascata

```
1. Keyring di sistema   → solo dove c'è un desktop (PC)
2. .env cifrato (age)   → consigliato su server/headless (hub Oracle)
3. Variabili ambiente   → Docker, CI
```

⚠️ **Caveat headless**: il keyring di sistema su Linux server non ha backend
(D-Bus/Secret Service assenti). Sull'hub Oracle la cascata parte dal
punto 2. La CLI `tramamind keys` deve rilevare l'ambiente e proporre
automaticamente l'opzione giusta.

Catalogo provider: [router/providers.yaml](../router/providers.yaml)
(versionato, senza segreti — le chiavi non ci passano mai).

## Flusso di una richiesta (hub)

```
richiesta (da OpenClaw / desktop remoto / CLI)
  → OmniRoute sull'hub
    1. edge online con il modello richiesto?  → edge (26B/27B)
    2. modello ≤4B servito localmente?        → vLLM hub
    3. altrimenti                             → fallback chain L3B
                                               (Google → Groq → NVIDIA →
                                                Cerebras → OpenRouter → Kimi)
```

Il failover 429/5xx con backoff resta invariato; l'edge è semplicemente
un provider in più nel registry, con healthcheck ogni 30 s: se il PC si
spegne, l'hub lo marca offline e instrada altrove senza errori visibili.

## Registrazione edge

```
POST /api/v1/edges/register
{
  "token": "<EDGE_TOKEN>",
  "models": ["gemopus-26b", "qwopus-27b"],
  "vram_free_gb": 20.5,
  "tailscale_ip": "100.x.y.z"
}
```

Retry automatico ogni 30 s se l'hub non risponde (PC acceso prima dell'hub,
o rete Tailscale in avvio). Healthcheck periodico con latenza e VRAM libera,
così OmniRoute può pesare l'edge nelle strategie latency_first/capability_based.

## Piano di implementazione (fasi)

- [x] Design + providers.yaml dichiarativo
- [ ] `router/config.py` — Pydantic Settings con cascata keyring/age/env
- [ ] `tramamind keys` — CLI interattiva gestione chiavi
- [ ] `router/topology/` — base/standalone (refactor dell'attuale)
- [ ] Endpoint registrazione edge in OmniRoute + client edge sul PC
- [ ] `tramamind topology` — wizard setup hub/edge
- [ ] deploy/docker-compose.hub.yml + docker-compose.edge.yml

Ogni fase entra nel repo solo quando è installabile e testata (regola 5).
