# Nodo always-on su Oracle Cloud Always Free

TramaMind 24/7 senza tenere il PC acceso: una VM ARM **VM.Standard.A1.Flex**
su Oracle Cloud, dentro i limiti Always Free.

> ⚠️ **Limiti aggiornati (giugno 2026):** l'Always Free ARM è stato dimezzato
> da 4 OCPU/24 GB a **2 OCPU / 12 GB** (1.500 OCPU-ore + 9.000 GB-ore/mese),
> enforcement dal 18 agosto 2026. Gli account PAYG sembrano mantenere 4/24
> gratis, ma Oracle non l'ha confermato ufficialmente: questa guida assume
> **2 OCPU / 12 GB**, che bastano. Storage invariato: 200 GB totali.

## Cosa gira sulla VM (budget RAM: 12 GB)

| Componente | RAM stimata | Note |
|---|---|---|
| Ollama + modello leggero (2B–4B Q4) | 3–4 GB | privacy locale, costo zero |
| OmniRoute :20128 | ~0,5 GB | routing + L2 (compressione/cache) |
| OpenClaw (container) | 2 GB | gateway Telegram |
| OS + Docker | ~1,5 GB | Ubuntu 24.04 ARM |
| **Margine** | ~4 GB | per picchi e aggiornamenti |

I modelli grossi (26B/27B) restano sul PC di casa: quando è acceso, OmniRoute
sulla VM può puntare anche a lui (via Tailscale) come provider aggiuntivo.

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

Lo script installa Docker, Ollama, configura UFW (solo SSH in ingresso) e
clona il repo in `~/tramamind`.

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
  usando il suo IP Tailscale → i modelli grossi diventano raggiungibili 24/7
  (fintanto che il PC è sveglio)

## 4. Avvio dello stack

```bash
cd ~/tramamind
./scripts/install.sh --pull-models   # scarica un modello leggero (≤4B Q4)
# compila .env con le chiavi delle API gratuite (Google, Groq, NVIDIA, Cerebras, OpenRouter)
./scripts/start-all.sh               # Ollama + OmniRoute
cd integrations/openclaw
cp .env.example .env                 # TELEGRAM_BOT_TOKEN da @BotFather
docker compose up -d                 # gateway L5b
```

Poi il pairing Telegram come da [integrations/openclaw/README.md](../integrations/openclaw/README.md).

## 5. Firewall OCI (Security List)

Di default la VCN Oracle ha regole restrictive: bene così. L'unica porta
necessaria in ingresso è la **22 (SSH)** — ancora meglio se ristretta al tuo
IP o sostituita da Tailscale SSH. **Non aprire** 20128, 11434, 18789.

## Limiti e avvertenze

- **Niente GPU**: l'inferenza locale è CPU-only. Un 4B Q4 su 2 OCPU ARM fa
  ~5–10 tok/s: ok per chat e heartbeat, non per coding intensivo. Per quello
  ci sono le API gratuite nella fallback chain.
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
