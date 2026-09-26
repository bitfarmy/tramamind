# benchmarks/ — misure, non stime

`benchmark.sh` invia i prompt di `prompts.txt` al router **due volte** e
registra provider, latenza e token in `data/benchmark-*.csv`:

- **giro 1** → misura routing + compressione;
- **giro 2** → stessi prompt: `token_input ≈ 0` significa cache hit.

```bash
./scripts/start-all.sh
./benchmarks/benchmark.sh
```

Richiede `jq` e lo stack avviato.

## Perché prompt fissi

I numeri di compressione e cache dipendono dal carico. Modifica
`prompts.txt` per avvicinarlo ai tuoi usi reali (una riga = un prompt):
è l'unico modo per avere dati che valgono per te.

## Prossimi passi (roadmap)

- A/B tra strategie di routing (stesso set di prompt, strategie diverse).
- Confronto compressione ON/OFF.
- Esportazione dei CSV verso `stats.sh` per analisi aggregate.
