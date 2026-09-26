# desktop/ — interfaccia (L5)

Fork di **Berd** con le estensioni TramaMind. *Fase 3 della roadmap: si
sviluppa solo quando PoC da terminale e tuning sono stabili.*

## Estensioni previste

- **Pannello VRAM modelli locali**: modelli caricati su Ollama, quantizzazione,
  VRAM occupata.
- **Toggle compressione ON/OFF**: pilota la pipeline di compressione di
  OmniRoute (oggi si fa dalla sua dashboard).
- **Selettore modalità**: `Locale` / `Cloud` / `Auto`.
- **Indicatore provenienza**: provider, modello, latenza e token per ogni
  risposta (stesse informazioni già mostrate da `scripts/chat.sh`).

## Integrazione

Il desktop parlerà con OmniRoute su `http://localhost:20128/v1`
(API OpenAI-compatibile). La provenienza arriva dai campi/header della
risposta, come documentato in [docs/architecture.md](../docs/architecture.md).

Nel frattempo: la CLI (`scripts/chat.sh`) offre lo stesso flusso da terminale.
