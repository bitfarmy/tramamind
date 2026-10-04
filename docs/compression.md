# Token

Il risparmio viene da non rispedire la storia.

A ogni turno TramaMind stima i token del pacchetto e quelli della trascrizione intera, con la stessa regola. Se la trascrizione sta nel tetto (`budget_tokens`, default 2500), parte tutta. Se non ci sta, un modello piccolo riassume le puntate vecchie e gli ultimi turni restano parola per parola. Dai turni vecchi vengono riattaccati, se c'è spazio, fino a quattro estratti: un blocco di codice, un unified diff, un traceback, o il risultato di un messaggio `tool`. Ognuno resta com'era, tagliato a 1500 caratteri. Un turno recente non viene tagliato.

La riga sotto la risposta distingue la stima dal numero vero dell'API, quando il provider lo manda. La percentuale è solo tra le due stime. `tramamind stats` fa la media sul log.

La compressione generica di OmniRoute (RTK, Caveman, LLMLingua) non è accesa da TramaMind. Può accorciare un prompt tagliando un nome o un vincolo. Se la attivi dalla dashboard di OmniRoute, falla su un benchmark tuo, non sui numeri di targa.

`tramamind proxy` applica la stessa stima prima di inoltrare `/v1/chat/completions`. La riga su stderr e le intestazioni `X-Tramamind-Raw-Tokens`, `X-Tramamind-Sent-Tokens` e `X-Tramamind-Saved-Pct` sono quel conto. Se l'upstream manda `prompt_tokens`, la riga aggiunge `· api N`. `tramamind demo` ristampa il conto di una chat finta. `tramamind pack trascrizione.json` lo fa sulla tua trascrizione, senza rete: con `--out` scrive i messaggi che partirebbero.
