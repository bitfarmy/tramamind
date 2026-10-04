# Catalogo Modelli Locali

Questi sono i tag Ollama dei preset. `cpu16` usa `gemma3:4b`, `qwen2.5-coder:3b` e `deepseek-r1:1.5b`. `gpu12` usa `qwen3:8b`, `qwen2.5-coder:7b` e `deepseek-r1:8b`. `gpu24` usa `qwen3:32b`, `qwen2.5-coder:14b` e `deepseek-r1:14b`. Il riassunto della chat usa sempre `gemma3:4b`.

I nomi Gemopus e Qwopus non sono modelli: non compaiono nel profilo.

---

## Perché modelli locali

- ✅ Gira in locale, zero costi per token
- ✅ Privacy totale, nessun dato esce dal PC
- ✅ Funziona offline
- ✅ Fallback finale quando le API gratuite esauriscono le quote
- ⚠️ Qualità inferiore alla frontiera su task lunghi e complessi
- ⚠️ Il contesto lungo richiede molta RAM/VRAM

---

## Famiglie consigliate

### Qwen (Apache 2.0) — codice e uso generale

| Modello Ollama | Parametri | VRAM indicativa (Q4) | Uso |
|---|---|---|---|
| `qwen2.5-coder:3b` | 3B | ~2 GB | Codice, macchine leggere |
| `qwen2.5-coder:7b` | 7B | ~5 GB | Codice, ottimo equilibrio |
| `qwen2.5-coder:14b` | 14B | ~9 GB | Codice, GPU consumer |
| `qwen2.5-coder:32b` | 32B | ~20 GB | Codice, GPU high-end |
| `qwen3:8b` | 8B | ~6 GB | Generale + ragionamento |
| `qwen3:14b` | 14B | ~10 GB | Generale + ragionamento |
| `qwen3:32b` | 32B | ~20 GB | Il meglio in locale su GPU consumer |

### Gemma 3 (Google) — generale e multimodale

| Modello Ollama | Parametri | VRAM indicativa (Q4) | Uso |
|---|---|---|---|
| `gemma3:1b` | 1B | ~1 GB | Risposte rapide, edge |
| `gemma3:4b` | 4B | ~3 GB | Uso generale leggero, multimodale |
| `gemma3:12b` | 12B | ~8 GB | Uso generale, buona qualità |
| `gemma3:27b` | 27B | ~17 GB | Alta qualità, GPU high-end |

### DeepSeek-R1 Distill — ragionamento

| Modello Ollama | Parametri | VRAM indicativa (Q4) | Uso |
|---|---|---|---|
| `deepseek-r1:1.5b` | 1.5B | ~1.5 GB | Ragionamento minimale |
| `deepseek-r1:8b` | 8B | ~6 GB | Ragionamento, ottimo equilibrio |
| `deepseek-r1:14b` | 14B | ~10 GB | Ragionamento avanzato |
| `deepseek-r1:32b` | 32B | ~20 GB | Massimo ragionamento locale |

> Le VRAM indicate sono per quantizzazione Q4, il default di Ollama. Q5/Q8 richiedono ~25–60% in più, BF16 circa 2 GB per miliardo di parametri.

---

## Scelta in base all'hardware

### Solo CPU / GPU integrata (8–16 GB RAM)
- `gemma3:4b`
- `qwen2.5-coder:3b`
- `deepseek-r1:1.5b`

### GPU consumer entry (RTX 3060 12 GB)
- `qwen2.5-coder:7b`
- `qwen3:8b`
- `deepseek-r1:8b`
- `gemma3:12b`

### GPU consumer high-end (RTX 4090 24 GB)
- `qwen3:32b`
- `qwen2.5-coder:32b`
- `deepseek-r1:32b`
- `gemma3:27b`

### GPU workstation (48+ GB VRAM)
- I 32B in quantizzazione alta (Q8/BF16)
- Modelli 70B (es. `llama3.3:70b`) in Q4
- Più modelli caricati simultaneamente

---

## Comandi Ollama

```bash
# Download
ollama pull qwen2.5-coder:7b

# Lista
ollama list

# Test
ollama run qwen2.5-coder:7b "Scrivi una funzione Python per..."

# Rimuovi
ollama rm qwen2.5-coder:7b

# Info
ollama show qwen2.5-coder:7b
```

---

## Modelfile personalizzato

Per ottimizzare un modello:

```dockerfile
FROM qwen2.5-coder:7b

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 32768

SYSTEM """
Sei un assistente preciso e conciso.
Rispondi in italiano.
Usa codice quando serve.
"""
```

Salva come `Modelfile.custom` e crea:

```bash
ollama create tramamind-coder -f Modelfile.custom
```

---

## Licenze

| Famiglia | Licenza | Uso commerciale |
|---|---|---|
| Qwen (2.5/3) | Apache 2.0 | ✅ Sì |
| Gemma 3 | Gemma Terms of Use | ✅ Sì, con condizioni Google |
| DeepSeek-R1 Distill | MIT (distill Qwen/Llama) | ✅ Sì |
| Llama 3.3 | Llama Community License | ✅ Sì, con condizioni Meta |

**Obbligo:** cita sempre i modelli originali nei crediti.

---

## Risorse

- Ollama Library: ollama.com/library
- Hugging Face: huggingface.co/models
