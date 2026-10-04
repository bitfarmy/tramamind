# Setup

Serve Python 3.10+ e Ollama. OmniRoute è opzionale.

```bash
./scripts/install.sh
.venv/bin/tramamind setup
.venv/bin/tramamind pull
.venv/bin/tramamind doctor
.venv/bin/tramamind chat
```

`setup` senza opzioni, da terminale, chiede il preset e le chiavi. Senza terminale interattivo:

```bash
tramamind setup --preset cpu16 --non-interactive
```

`--pull` nello stesso comando scarica i modelli. `--force` riscrive i tag se il profilo c'è già.

La pagina di configurazione è `tramamind ui`: preset, chiavi mascherate, scheda, chat. Ascolta solo `127.0.0.1:8787`. Dalla stessa pagina si impostano tetto e turni interi, si sceglie Ollama o OmniRoute, e si avvia il proxy. L'indirizzo da incollare nel client è `http://127.0.0.1:8788/v1`. Sotto compare l'ultima riga dei token.

Per un client OpenAI-compatible (Cursor, Continue) il proxy è un altro comando, sulla porta `8788`:

```bash
tramamind proxy
# base URL: http://127.0.0.1:8788/v1
# a monte, di default: http://127.0.0.1:11434/v1
```

`tramamind demo` stampa il conto dei token su una chat di esempio e non ha bisogno di Ollama. `tramamind pack sessione.json` fa il conto su un file di messaggi. Da un altro ambiente Python:

```bash
pipx install "git+https://github.com/bitfarmy/tramamind"
```

Oppure, da questo repository, `pipx install .`.

Per Groq: https://console.groq.com/keys e poi `tramamind keys add groq`. L'escalation usa l'API OpenAI-compatible di Groq, senza passare da OmniRoute.

Per più provider insieme: `npm install -g omniroute`, `tramamind keys add …`, `tramamind sync`, `tramamind up`. Il profilo tiene `escalation.transport: auto`, quindi se OmniRoute risponde si usa quello, altrimenti Groq.

File:

| Percorso | Cosa c'è |
|---|---|
| `~/.config/tramamind/profile.yaml` | preset, tetto, modello cloud |
| `~/.config/tramamind/card.md` | fatti stabili |
| keyring / `secrets.age` / `.env` | chiavi, mai nel git |
| `~/.local/share/tramamind/sessions` | chat |
