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
├── vLLM (Qwen3-4B)         ~4 GB   (weights + KV cache 8k)
├── Entropy Gate            ~1 GB
├── OmniRoute               ~0.5 GB
└── Buffer                  ~4.5 GB
```

## Policy modelli sul nodo Oracle

| Modello | Verdetto | Motivo |
|---|---|---|
| **GPT-5-Distill-Qwen3-4B** (~3 GB) | ✅ **primario** | comodo, restano ~7–8 GB liberi |
| **Gemini3.5-Code-Reasoner-2B** (~1.5 GB) | ✅ **fast lane** | ideale per task veloci e heartbeat |
| Qwen3.5-9B-Claude-Opus-Distill-v2 (~6 GB) | ❌ escluso | pesi + KV cache lasciano ~4–5 GB per sistema + context: troppo rischioso |
| Gemopus 26B / Qwopus 27B | ❌ solo PC locale | 16–17 GB ciascuno, impossibili su 12 GB |

Su Oracle il runtime è **vLLM** (CPU backend): serve il 4B come modello
default e il 2B per i task veloci. Su ARM64, se la build vLLM dovesse dare
problemi, il fallback documentato è llama.cpp/Ollama con gli stessi pesi.

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

Lo script installa Docker, vLLM (CPU), configura UFW (solo SSH in ingresso),
scarica i due modelli approvati (4B + 2B) e clona il repo in `~/tramamind`.

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
./scripts/start-all.sh               # vLLM + Entropy Gate + OmniRoute
cd integrations/openclaw
cp .env.example .env                 # TELEGRAM_BOT_TOKEN da @BotFather
docker compose up -d                 # gateway L5b
```

Poi il pairing Telegram come da [integrations/openclaw/README.md](../integrations/openclaw/README.md).

## 5. Firewall OCI (Security List)

Di default la VCN Oracle ha regole restrictive: bene così. L'unica porta
necessaria in ingresso è la **22 (SSH)** — ancora meglio se ristretta al tuo
IP o sostituita da Tailscale SSH. **Non aprire** 20128, 11434, 18789, 9090.

## Limiti e avvertenze

- **Niente GPU**: inferenza CPU-only su 2 OCPU ARM. Il 4B fa ~5–10 tok/s:
  ok per chat e heartbeat, non per coding intensivo — per quello ci sono le
  API gratuite nella fallback chain.
- **KV cache contenuta**: context limitato a 8k sul nodo Oracle (è già nei
  4 GB allocati a vLLM). Per context lunghi, il router deve preferire le API
  cloud o il PC locale.
- **ARM64**: le immagini Docker devono essere multi-arch. Se un'immagine
  manca per arm64, aggiungi `platform: linux/arm64` nel compose o cercane
  l'alternativa ARM.
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
