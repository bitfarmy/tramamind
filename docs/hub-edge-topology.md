# Topologia hub/edge — registro decisioni

> La specifica completa è in [cloud-implementation.md](cloud-implementation.md).
> Questo file registra solo le **decisioni** prese e il perché, in ordine
> cronologico, per non doverle rinegoziare a ogni sessione.

## Decisioni

1. **Mono-repo** — niente repo separato `tramamind-cloud`: tutto vive in
   `tramamind` (`deploy/`, `router/`, `cli/`, `docs/`).
2. **Porte** — OmniRoute **20128** (come da repo), Entropy Gate **9090**,
   vLLM **8000**, Ollama **11434**. La bozza iniziale (8080/11434 per vLLM)
   è stata corretta.
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
7. **Entropy Gate = servizio separato su 9090** (non integrato in OmniRoute):
   il README principale è stato allineato di conseguenza.
8. **vLLM su ARM64** — immagine ufficiale x86-only: build da sorgente o
   fallback Ollama/llama.cpp. Deciso in fase di provisioning.
9. **Implementazione per fasi** — regola 5: entra nel repo solo ciò che è
   installabile e testato. Design e config dichiarativi (providers.yaml)
   fanno eccezione perché sono la documentazione dell'implementazione.
