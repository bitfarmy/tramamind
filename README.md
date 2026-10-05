# TramaMind

[![PyPI](https://img.shields.io/pypi/v/tramamind?color=e6a15c&label=pypi)](https://pypi.org/project/tramamind/)
[![MIT](https://img.shields.io/badge/license-MIT-b7ab9a)](LICENSE)

Shows the tokens it refused to send.

Recent turns stay whole, however long they are. From older turns it keeps up to four pieces, word for word: a code block, a unified diff, a traceback, or a tool result. Each piece is at most 1500 characters, and only while it fits. One cloud call, and only when the local answer is empty, a short refusal, or you ask to redo it.

```bash
pipx install tramamind
tramamind demo
```

`demo` needs no model. On the sample chat it prints:

```
full history ~10273 · packet ~1211 · −88%
code kept verbatim: def add(a, b)
last user message kept: What does add return?
```

The old turns in that sample are the same sentence repeated, which is why the gap is wide. `def add` comes from those old turns and is still in the packet. The last question is the original message. A long source file in the latest turns is sent whole, and the percentage gets smaller. The figure is this estimate (about 3.5 characters per token), on this chat.

```
your client
      │
      ▼
packet, under the budget ──► Ollama
      │
      └─ once, if the local answer fails ──► Groq, or OmniRoute
```

To follow `main` instead of this release: `pipx install "git+https://github.com/bitfarmy/tramamind"`.

## On your own transcript

```bash
tramamind pack session.json
```

The file is a JSON array of messages, or an object with a `messages` key. The line is the one the proxy prints (`storia intera`, `inviati`, the percentage), then the blocks that stayed. `--out packet.json` writes the messages that would be forwarded. Nothing is sent to a model.

## In front of Cursor, Continue, or any OpenAI client

```bash
tramamind proxy
```

OpenAI base URL: `http://127.0.0.1:8788/v1`

Default upstream: Ollama at `http://127.0.0.1:11434/v1`. OmniRoute, if you use it, is `--upstream http://127.0.0.1:20128/v1`. The chat page stays on port 8787.

```yaml
# Continue
name: TramaMind
provider: openai
model: qwen2.5-coder:7b
apiBase: http://127.0.0.1:8788/v1
apiKey: ollama
```

Each request prints a line on stderr, and the response carries `X-Tramamind-Raw-Tokens`, `X-Tramamind-Sent-Tokens`, and `X-Tramamind-Saved-Pct`. When the upstream sends `prompt_tokens`, the same line gains `· api N` and the response gains `X-Tramamind-Api-Prompt-Tokens`. The summary is an excerpt, so the model already loaded for the client stays loaded. Your system message stays as it arrived. The log stores the counts.

`--budget` defaults to 2500 estimated tokens and `--verbatim` to the last 6 messages. With a profile, those two values come from `~/.config/tramamind/profile.yaml`.

## Chat on this machine

```bash
tramamind ui
```

http://127.0.0.1:8787 sets the token budget, chooses Ollama or OmniRoute, starts the proxy, and shows the last savings line.

From a clone:

```bash
./scripts/install.sh
.venv/bin/tramamind setup
.venv/bin/tramamind pull
.venv/bin/tramamind chat
```

## In italiano

Assistente personale sul tuo PC. Il modello di default è locale, via Ollama. La chat ricorda le sessioni e, quando la storia si allunga, ne manda un riassunto più gli ultimi turni, non la trascrizione intera. Se la risposta locale è vuota, è una scusa, o chiedi di rifarla, parte **una** chiamata cloud.

OmniRoute, se lo installi, resta il tubo verso più provider. TramaMind non è un secondo router: decide cosa entra nel prompt e quale modello locale usare.

```
tramamind chat
      │
      ▼
pacchetto con tetto ──► Ollama
      │
      └─ solo se serve ──► Groq diretto, oppure OmniRoute
```

Ollama da solo non tiene un tetto sulla storia e non cambia modello in base alla domanda. OmniRoute da solo non sceglie i modelli per la tua RAM e non distingue una risposta scarsa da un errore HTTP. TramaMind fa quelle due cose e lascia il resto a loro.

`tramamind proxy` mette lo stesso pacchetto davanti a Cursor, Continue o a qualsiasi client compatibile con OpenAI. `tramamind demo` mostra il conto senza scaricare un modello. `tramamind pack sessione.json` fa lo stesso conto sulla tua trascrizione.

Claude Pro non passa di qui. Per il codice serio resta Claude Code, diretto.

```bash
./scripts/install.sh
.venv/bin/tramamind setup          # preset in base alla RAM, chiavi opzionali
.venv/bin/tramamind pull           # scarica i tag del preset
.venv/bin/tramamind chat
```

Pagina locale, solo su questa macchina: `tramamind ui` poi http://127.0.0.1:8787. Da lì partono anche tetto, upstream e il proxy su `http://127.0.0.1:8788/v1`.

Corsie: `tramamind chat --code "…"`, `--think`, `--fast`. In chat: `/new`, `/sessions`, `/resume`, `/use code`, `/clear`.

Sotto ogni risposta c'è il conto: token inviati, stima della storia intera, e la percentuale tolta dal pacchetto quando c'è stato un riassunto. `tramamind stats` aggrega quei conti, senza il testo.

`tramamind doctor` dice cosa manca. Se Ollama non risponde, il comando fallisce: non stampa "attivo" lo stesso.

### Preset

| Preset | Quando | Generale | Codice | Ragionamento |
|---|---|---|---|---|
| `cpu16` | portatile, 16 GB | `gemma3:4b` | `qwen2.5-coder:3b` | `deepseek-r1:1.5b` |
| `gpu12` | GPU ~12 GB | `qwen3:8b` | `qwen2.5-coder:7b` | `deepseek-r1:8b` |
| `gpu24` | GPU 24 GB | `qwen3:32b` | `qwen2.5-coder:14b` | `deepseek-r1:14b` |

Il tag `summary` del profilo è `gemma3:4b`. Viene chiamato solo se è già il modello della risposta (è il caso di `cpu16`). Sugli altri preset il riassunto è estrattivo, per non ricaricare un modello a ogni messaggio. Il proxy è sempre estrattivo. I tag sono quelli di [docs/local-models.md](docs/local-models.md).

### Chiavi

`tramamind keys add groq` le mette nel keyring (oppure in un file age, oppure in `~/.config/tramamind/.env` con permessi `0600`). Con una chiave Groq l'escalation funziona anche senza OmniRoute. `tramamind sync` spinge le chiavi nel CLI di OmniRoute, se c'è.

Il modello cloud di default nel profilo è `openai/gpt-oss-120b`. Se quel catalogo cambia, lo sostituisci in `~/.config/tramamind/profile.yaml`.

### Cosa non fa

Il risparmio è il pacchetto: ultimi turni interi, e dai turni vecchi un estratto più fino a quattro pezzi parola per parola (codice, diff, traceback, risultato di un tool) se ci stanno. Ogni pezzo vecchio è al massimo 1500 caratteri. La compressione di OmniRoute, se la accendi dalla sua dashboard, è un'altra cosa e può tagliare proprio il pezzo che serviva. Il numero di cui mi fido è quello stampato da `tramamind chat`, da `tramamind demo`, da `tramamind pack` e dal proxy. Quando il provider manda `prompt_tokens`, la riga del proxy lo affianca alla stima.

OpenHands e OpenClaw sono extra, spenti. L'app desktop e il nodo Oracle non fanno parte del flusso: gli appunti sono in [docs/future/](docs/future/).

Licenza MIT. Uso personale delle API gratuite: [docs/legal.md](docs/legal.md).
