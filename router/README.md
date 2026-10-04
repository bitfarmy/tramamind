# Cosa c'è qui

`packet.py` costruisce il prompt. `engine.py` fa un turno. `proxy.py` applica lo stesso pacchetto a un client OpenAI-compatible. `keystore.py` tiene le chiavi. `profile.py` è l'unico file di configurazione. `runtime.py` avvia i processi e spinge le chiavi a OmniRoute.

Ollama è il runtime locale. OmniRoute, se presente, è solo il tubo cloud. Non c'è un catalogo di ID modello ricopiato: i tag locali sono i preset, l'ID cloud sta nel profilo e lo cambi tu quando il provider lo cambia.
