# Topologia hub/edge — registro decisioni

> La specifica completa è in [cloud-implementation.md](cloud-implementation.md).
> Questo file registra solo le **decisioni** prese e il perché, in ordine
> cronologico, per non doverle rinegoziare a ogni sessione.

## Decisioni

1. **Mono-repo** — niente repo separato `tramamind-cloud`: tutto vive in
   `tramamind` (`deploy/`, `router/`, `cli/`, `docs/`).
2. **Porte** — OmniRoute **20128** (come da repo), vLLM **8000**, Ollama
   **11434**. La bozza iniziale (8080/11434 per vLLM) è stata corretta.
3. **Modelli hub** — GPT-5-Distill-Qwen3-4B (primario) + Gemini3.5-Code-Reasoner-2B
   (fast). **Qwen3.5-9B escluso**: su 12 GB lascerebbe ~4–5 GB per sistema e
   context. 26B/27B solo edge.
4. **Rete** — Tailscale-only di default, zero porte pubbliche oltre SSH.
   Caddy + dominio + token come opzione documentata, non default.
5. **Chiavi** — cascata keyring → age → env. Keyring solo dove c'è desktop;
   sull'hub headless si parte da age. Token edge in `auth.yaml` cifrato,
   mai in config.yaml in chiaro.
6. **Niente speedtest alla registrazione edge** — la latenza reale si misura
   dagli healthcheck periodici (30 s), non da un test una tantum.
7. **L2 = integrato in OmniRoute** (decisione verificata il 2026-09-29 su
   `docs/compression.md`, `docker-compose.yml`, `router/README.md` e
   `.env.example`): pipeline a 12 motori + cache semantica, toggle da
   Dashboard → Compression. La dicitura "Entropy Gate separato su :9090"
   presente nei documenti di progetto precedenti era **superata**: non
   esiste alcun proxy L2 né alcuna porta 9090. I budget RAM del nodo Oracle
   sono stati corretti di conseguenza (OmniRoute+L2 ~1.5 GB).
8. **vLLM su ARM64** — immagine ufficiale x86-only: build da sorgente o
   fallback Ollama/llama.cpp. Deciso in fase di provisioning.
9. **Implementazione per fasi** — regola 5: entra nel repo solo ciò che è
   installabile e testato. Design e config dichiarativi (providers.yaml)
   fanno eccezione perché sono la documentazione dell'implementazione.
10. **Budget hub 4 OCPU / 24 GB + runtime Ollama/GGUF** (2026-09-30) —
   la tenancy è PAYG e mantiene i limiti pre-giugno-2026 (3.000 OCPU-ore +
   18.000 GB-ore/mese = 4 OCPU/24 GB sempre accesi, gratis): il banner in
   console lo conferma. Conseguenze: la decisione 3 è superata nella parte
   "9B escluso" — il **Qwen3.5-9B-Claude-Opus-Distill-v2 torna sull'hub come
   primario**; il runtime hub è **Ollama con GGUF** (il 9B/4B in bf16 su
   vLLM-CPU non avrebbe senso: pesi doppi e più lenti su ARM), quindi la
   porta 8000/vLLM della decisione 2 non è più usata sull'hub. Account
   free-only a 2 OCPU/12 GB: vale il vecchio budget (4B+2B, niente 9B),
   documentato in oracle-free-tier.md.
