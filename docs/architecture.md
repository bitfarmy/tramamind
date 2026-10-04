# Come è fatto

Tre pezzi.

1. **Il pacchetto.** `router/packet.py` tiene gli ultimi turni interi e mette il resto in un riassunto. Il tetto di default è 2500 token stimati (circa 3,5 caratteri per token, la stessa stima per il pacchetto e per la storia intera). Se la stima della storia sta nel tetto, non si riassume niente. Il riassunto lo scrive il modello solo quando è lo stesso tag della risposta, così Ollama non scarica un secondo modello a ogni turno. Negli altri preset il riassunto è estrattivo. Dai turni vecchi restano, se ci stanno, fino a quattro estratti parola per parola: codice, diff, traceback, risultato di un tool.
2. **Il modello locale.** Ollama, tag scelti dal preset. Codice, ragionamento e chat generale sono tre tag diversi. La scelta è una regola sul testo (`refactor`, un blocco di codice, "passo passo"), non un classificatore.
3. **Una escalation.** Groq diretto se c'è la chiave, altrimenti OmniRoute se è acceso. Parte se Ollama non risponde, se la risposta è vuota o è una scusa breve, o se scrivi "rifallo meglio". Una volta per messaggio. Poi ci si ferma.

Lo stesso pacchetto è un proxy OpenAI-compatible: `tramamind proxy` ascolta su `127.0.0.1:8788` e inoltra a Ollama o all'upstream che indichi. Il riassunto del proxy è sempre estrattivo, così non carica un secondo modello. `tramamind demo` stampa il conto su una chat finta. `tramamind pack` lo stampa su una trascrizione JSON. Nessuno dei due comandi chiama un modello.

Le sessioni stanno in `~/.local/share/tramamind/sessions`. La scheda stabile è `~/.config/tramamind/card.md`: le righe che iniziano con `#` non vengono inviate. Il log `requests.jsonl` registra modello, tempi e token, non il testo.

OmniRoute, quando c'è, riceve le chiavi da `tramamind sync` (`omniroute setup --add-provider`). L'heap di default è 1024 MB, abbastanza per la chat. Non si alza a 8 GB da solo.

`tramamind up` avvia Ollama se è spento, e OmniRoute solo se c'è almeno una chiave cloud e il binario è installato. `tramamind down` ferma solo i processi che ha avviato lui.
