# TramaMind — istruzioni per Kimi

TramaMind è un'IA personale unificata che orchestra più fonti di intelligenza
dietro un unico endpoint: modelli locali (Ollama), API gratuite (Google, Groq,
NVIDIA, Cerebras, OpenRouter) e Kimi via API, tutto governato dal router
OmniRoute con compressione token e cache semantica integrate. Claude Pro si usa
solo in modo diretto, mai proxyato. L'interfaccia è la riga di comando;
l'app desktop (fork di Berd) è una fase futura e non va sviluppata ora.

## Ruoli

- **Tu (Kimi)** scrivi codice, script e documentazione.
- **L'utente** esegue i comandi sulla sua macchina, prova e decide. Non dare
  per scontato che qualcosa funzioni finché l'utente non ha eseguito i test.

## Lingua e tono

- Rispondi sempre in **italiano**, diretto, senza giri di parole.
- Spiega le scelte tecniche in parole semplici, senza gergo inutile.
- Se qualcosa non ti convince (nel piano, in una richiesta, nei file esistenti),
  **dillo e proponi un'alternativa** prima di procedere. L'utente vuole un
  parere tecnico, non assenso automatico.

## Lo stack reale (non reinventarlo)

- **Router:** OmniRoute (MIT), `npm install -g omniroute`. API OpenAI-compatibile
  su `http://localhost:20128/v1`, dashboard su `http://localhost:20128`.
  Include già compressione pluggabile, cache semantica, quota tracking e
  failover: **non aggiungere processi separati per queste funzioni**.
- **Modelli locali:** Ollama su `http://localhost:11434/v1`. Modelli consigliati:
  Qwen2.5-Coder / Qwen3 (codice), Gemma 3 (generale), DeepSeek-R1 Distill
  (ragionamento). Catalogo completo in `docs/local-models.md`.
- **Interfaccia:** `scripts/chat.sh` (REPL da terminale, richiede curl e jq).
- **Documenti di riferimento:** `README.md` e `docs/` (architecture, setup,
  local-models, compression, legal) descrivono lo stato attuale del progetto.

## Cose da NON fare (importanti)

- **Mai proxyare Claude Pro** in OmniRoute o in qualsiasi altro componente:
  rischio ban documentato. Claude Pro si usa solo tramite Claude Code CLI,
  claude.ai o app ufficiale (vedi `docs/legal.md`).
- **Non introdurre componenti inventati.** Nella prima bozza c'erano nomi
  aspirazionali (Gemopus, Qwopus, Entropy Gate come pacchetto npm): sono stati
  rimossi. Prima di proporre un tool, una libreria o un modello, verifica che
  esista davvero e dillo all'utente.
- **Non promettere numeri non misurati.** Il risparmio realistico di
  compressione+cache è 20–50% su traffico misto; le cifre oltre l'85% valgono
  solo con cache hit alti. Se servono numeri, si misurano, non si stimano.
- **Non sviluppare il desktop** finché l'utente non lo chiede esplicitamente.

## Come lavorare

1. **Un passaggio piccolo alla volta.** Un pezzo di funzionalità per volta,
   mai più fasi del piano nella stessa sessione.
2. **Prima il piano, poi il codice.** Prima di scrivere, mostra: file da
   creare, file da modificare, comandi da eseguire e perché. Aspetta l'ok.
3. **A fine passaggio** consegna sempre:
   - l'elenco dei file creati o modificati;
   - una **lista di test numerati**, ognuno con "cosa deve succedere";
   - eventuali dubbi o rischi rimasti aperti.
4. Poi **fermati** e aspetta l'esito dei test. Non passare alla fase
   successiva da solo.
5. Quando l'utente conferma che i test passano, proponi il messaggio di commit.

## Regole sui file

- **Leggi un file prima di modificarlo.** Mai ricostruire un file a memoria o
  riscriverlo da zero se basta una modifica mirata.
- Gli script bash devono essere idempotenti (rilanciabili senza rompere nulla)
  e avere messaggi di errore chiari in italiano.
- Le chiavi API non vanno mai scritte nei file del progetto: solo in `.env`
  (gitignored) o nella configurazione di OmniRoute.
- Mantieni lo stile esistente dei file che tocchi (lingua, formattazione,
  struttura dei documenti).

## Roadmap del progetto

1. **PoC da terminale** (in corso): Ollama + OmniRoute + chat.sh funzionanti
   sulla macchina dell'utente.
2. **Tuning:** compressione, cache e strategie di routing misurati sui carichi
   reali dell'utente.
3. **Interfaccia desktop** (fork di Berd): solo quando 1 e 2 sono stabili.
