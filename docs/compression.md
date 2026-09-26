# Compressione e cache (L2)

La compressione in TramaMind è **integrata in OmniRoute**: nessun proxy
separato, nessuna porta extra. Si configura dalla dashboard
(`http://localhost:20128`) e si misura con `benchmarks/benchmark.sh`.

## Pipeline di compressione

OmniRoute include una pipeline a 12 motori componibili. I principali:

| Motore | Cosa fa |
|---|---|
| **Session-Dedup** | Elimina contenuti già inviati nella sessione |
| **Lite** | Pulizia conservativa lossless |
| **RTK** | Filtra e deduplica output di comandi/tool |
| **Headroom** | Compattazione reversibile di tabelle e dati strutturati |
| **Relevance** | Tiene le frasi più rilevanti per l'ultima domanda |
| **Caveman** | Condensazione rule-based della prosa |
| **LLMLingua-2** | Pruning semantico code-safe (worker isolato) |
| **Ultra** | Stadi ad alto risparmio con guardie di preservazione |

Esempio documentato da OmniRoute:

```
Prima (69 token):  "The function should iterate over the list of items,
                    and for each item, it should check whether the value
                    is greater than zero, and if so, add it to the
                    running total."
Dopo  (19 token):  "sum all list items where value > 0"
```

## Cache semantica

Due livelli (signature + semantica). Le risposte non-streaming con
`temperature=0` vengono cacheate automaticamente; una richiesta semanticamente
equivalente a una precedente viene servita dalla cache: **zero chiamate
upstream, zero token**.

Bypass puntuale con l'header `X-OmniRoute-No-Cache: true`.

## Aspettative oneste

| Scenario | Risparmio token realistico |
|---|---|
| Traffico misto (chat + codice + ricerca) | **20–50%** |
| Carichi tool-heavy / ripetitivi | fino a ~89% (caso documentato) |
| Cache hit alti (stesse domande, sessioni lunghe) | oltre l'85% |

Il dato di targa "15–95%" di OmniRoute dipende dal carico: **misura sui tuoi
prompt**, non fidarti delle stime.

## Misurare, non stimare

```bash
./scripts/start-all.sh
./benchmarks/benchmark.sh
```

`benchmark.sh` manda i prompt di `benchmarks/prompts.txt` **due volte**:

- **giro 1** → misura routing + compressione;
- **giro 2** → stessi prompt: `token_input ≈ 0` significa cache hit.

Risultati in `data/benchmark-*.csv`. Modifica `prompts.txt` per avvicinarlo
ai tuoi carichi reali: è l'unico modo per avere numeri che valgono.

## Quando disattivarla

- Benchmark e valutazioni dove serve il prompt esatto.
- Debug del router (traffico grezzo).
- Output creativi dove la condensazione taglierebbe troppo.

Il toggle si fa dalla dashboard di OmniRoute (sezione Compression).
