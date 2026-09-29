# Nodo always-on su Oracle Cloud Always Free

TramaMind 24/7 senza tenere il PC acceso: una VM ARM **VM.Standard.A1.Flex**
su Oracle Cloud, dentro i limiti Always Free.

> ⚠️ **Limiti aggiornati (giugno 2026):** l'Always Free ARM è stato dimezzato
> da 4 OCPU/24 GB a **2 OCPU / 12 GB** (1.500 OCPU-ore + 9.000 GB-ore/mese),
> enforcement dal 18 agosto 2026. Gli account PAYG sembrano mantenere 4/24
> gratis, ma Oracle non l'ha confermato ufficialmente: questa guida assume
> **2 OCPU / 12 GB**. Storage invariato: 200 GB totali.

## Allocazione RAM su Oracle (12 GB)

```
Oracle A1 (2 OCPU / 12 GB)
├── Sistema + Docker        ~2 GB
├── Modello primario (GGUF) ~4 GB   (4B Q4_K_M + context 8k)
├── OmniRoute (L2 incluso)  ~1.5 GB
└── Buffer                  ~4.5 GB
```

> L2 (compressione + cache semantica) è integrato in OmniRoute: nessun
> servizio né budget RAM separato. Vedi [compression.md](compression.md).

## Policy modelli sul nodo Oracle

I distillati sono **modelli pubblici della community su HuggingFace**
(autori: Jackrong, 11-47) — niente da caricare, la VM li scarica da sola.

| Nome nel progetto | Repo HuggingFace | Verdetto |
|---|---|---|
| GPT-5-Distill-Qwen3-4B | `Jackrong/GPT-5-Distill-Qwen3-4B-Instruct` (+ `-GGUF`) | ✅ **primario** (GGUF Q4_K_M ~2,5 GB) |
| Gemini3.5-Code-Reasoner-2B | `11-47/Gemini3.5-Code.Reasoner-2b` | ✅ **fast lane** (heartbeat, task veloci) |
| Qwen3.5-9B-Claude-Opus-Distill-v2 | `Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2` | ❌ escluso da Oracle (budget RAM) |
| Gemopus 26B-A4B | `Jackrong/Gemopus-4-26B-A4B-it-GGUF` | ❌ solo PC locale (16+ GB) |
| Qwopus 27B | `Jackrong/Qwopus3.6-27B-Coder` | ❌ solo PC locale (16+ GB) |

> **Runtime su Oracle: Ollama/llama.cpp con GGUF**, non vLLM. Il 4B in
> safetensors bf16 occupa ~8 GB e sfora il budget; il GGUF Q4_K_M ne occupa
> ~2,5 e su CPU ARM è nettamente più veloce. vLLM resta utile solo su
> macchine x86 con più RAM.

## PC locale (16+ GB) — modelli pesanti

```
PC Locale (16+ GB)
├── Ollama (Gemopus 26B)    ~16 GB
├── Qwopus 27B              ~17 GB
└── Desktop                 ~2 GB
```

Quando il PC è acceso, OmniRoute su Oracle lo raggiunge via **Tailscale**
e lo usa come provider aggiuntivo: i 26B/27B diventano disponibili da
remoto senza esporre porte.

## 1. Crea la VM

1. Registrati su [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
   (carta di credito per verifica, niente addebiti se resti nei limiti)
2. **Subito dopo**: Billing → Budgets → crea un budget alert a **1 $**
   (se Oracle dovesse mai contabilizzare qualcosa, lo sai immediatamente)
3. Compute → Instances → Create instance:
   - Shape: **Ampere VM.Standard.A1.Flex** → 2 OCPU / 12 GB
   - Image: **Ubuntu 24.04 (aarch64)**
   - Boot volume: 100 GB (dentro i 200 GB free)
   - Networking: VCN default, **assegna IP pubblico**
   - SSH: carica la tua chiave pubblica
4. Se compare "Out of capacity": riprova in orari morti, cambia fault domain,
   oppure valuta l'upgrade a PAYG (resta gratis nei limiti, capacità prioritaria)

## 2. Provisioning

```bash
ssh ubuntu@<IP-PUBBLICO>
curl -fsSL https://raw.githubusercontent.com/bitfarmy/tramamind/main/scripts/oracle-setup.sh | bash
```

Lo script installa Docker e Ollama, scarica i due modelli approvati
(4B primario in GGUF Q4_K_M + 2B fast), configura UFW (solo SSH in ingresso),
aggiunge 4 GB di swap e clona il repo in `~/tramamind`.

### Import dei GGUF in Ollama (dopo il provisioning)

```bash
cd ~/.cache/huggingface/hub/models--Jackrong--GPT-5-Distill-Qwen3-4B-Instruct-GGUF/snapshots/*/
cat > Modelfile <<'EOF'
FROM ./GPT-5-Distill-Qwen3-4B-Instruct_Q4_K_M.gguf
PARAMETER num_ctx 8192
EOF
ollama create gpt-5-distill-qwen3-4b -f Modelfile
ollama run gpt-5-distill-qwen3-4b "ciao"   # smoke test
```

## 3. Rete privata con Tailscale (consigliato)

OmniRoute **non deve essere esposto su Internet**. Con Tailscale la VM e il
tuo PC/telefono sono sulla stessa rete privata:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

- OmniRoute resta in ascolto su localhost/Tailscale, mai pubblico
- OpenClaw non ha bisogno di porte in ingresso: parla con Telegram in uscita
- Quando il PC di casa è acceso, aggiungilo come provider in OmniRoute
  usando il suo IP Tailscale → Gemopus/Qwopus raggiungibili da remoto

## 4. Avvio dello stack

```bash
cd ~/tramamind
# compila .env con le chiavi delle API gratuite (Google, Groq, NVIDIA, Cerebras, OpenRouter)
./scripts/start-all.sh               # Ollama + OmniRoute (L2 incluso)
cd integrations/openclaw
cp .env.example .env                 # TELEGRAM_BOT_TOKEN da @BotFather
docker compose up -d                 # gateway L5b
```

Poi il pairing Telegram come da [integrations/openclaw/README.md](../integrations/openclaw/README.md).

## 5. Firewall OCI (Security List)

Di default la VCN Oracle ha regole restrictive: bene così. L'unica porta
necessaria in ingresso è la **22 (SSH)** — ancora meglio se ristretta al tuo
IP o sostituita da Tailscale SSH. **Non aprire** 20128, 8000, 11434, 18789.

## Limiti e avvertenze

- **Niente GPU**: inferenza CPU-only su 2 OCPU ARM. Il 4B fa ~5–10 tok/s:
  ok per chat e heartbeat, non per coding intensivo — per quello ci sono le
  API gratuite nella fallback chain.
- **Context contenuto**: `num_ctx 8192` sul nodo Oracle (è già nei 4 GB
  allocati). Per context lunghi, il router deve preferire le API cloud o il
  PC locale.
- **ARM64**: le immagini Docker devono essere multi-arch. Se un'immagine
  manca per arm64, aggiungi `platform: linux/arm64` nel compose o cercane
  l'alternativa ARM.
- **Licenze dei distillati**: ogni repo HF ha la sua licenza (Gemma/Qwen
  derivate). Uso personale OK; prima di qualsiasi redistribuzione controlla
  la model card del singolo repo. Vedi [legal.md](legal.md).
- **"Always Free" non è un contratto**: Oracle ha già dimezzato i limiti una
  volta senza preavviso. Il budget alert a 1 $ è obbligatorio, e il repo è
  portabile: se Oracle dovesse peggiorare ancora, lo stesso setup si sposta
  su un mini PC in 30 minuti.
- **Reclaim**: le VM free palesemente inattive possono essere reclamate.
  Con OmniRoute + heartbeat OpenClaw attivi non è un problema, ma un cron
  leggero (es. healthcheck ogni ora) è un'ulteriore assicurazione.

## Costi

0 €/mese entro i limiti Always Free. Unico costo potenziale: superamento
limiti su account PAYG → evitato dal budget alert.
