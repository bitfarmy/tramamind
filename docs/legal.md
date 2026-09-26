# Note legali e condizioni d'uso

> Questo documento non è consulenza legale. È la sintesi operativa delle
> regole che TramaMind si impone per restare nei ToS dei provider.

## Regola 0 — Uso personale

TramaMind è uno stack **personale**. È vietato:

- **rivendere** l'accesso o le risposte,
- **automazione massiva** (scraping di tier gratuiti, account multipli,
  rotazione di chiavi per aggirare i limiti).

Sia perché viola i ToS dei provider, sia perché danneggia la community
che quei tier gratuiti li mantiene aperti.

## Claude Pro — SOLO diretto, MAI proxyato

- Claude Pro si usa **esclusivamente** tramite Claude Code CLI, claude.ai o
  app ufficiale.
- **Mai** instradare l'abbonamento Pro attraverso OmniRoute o qualsiasi
  altro proxy: violazione dei ToS Anthropic → **rischio ban documentato**.
- TramaMind non include e non includerà Claude Pro nella catena di failover.
  Se serve Claude via API, si usa una chiave API Anthropic a consumo
  (configurazione separata, a pagamento).

## Kimi

Accesso legittimo via API ufficiale su `platform.moonshot.ai`, con la
propria chiave (`KIMI_API_KEY`). OmniRoute lo supporta come provider
first-class. Nessun scraping dell'interfaccia web.

## API gratuite (L3B)

I tier gratuiti di Google AI Studio, Groq, NVIDIA NIM, Cerebras e OpenRouter
sono soggetti a rate limit e ToS specifici:

- rispetta i rate limit (il failover di OmniRoute gestisce i `429`, non li
  aggira),
- una chiave = una persona,
- controlla periodicamente i ToS: possono cambiare.

## Modelli locali

I modelli in [local-models.md](local-models.md) hanno licenze proprie:

| Famiglia | Licenza | Uso commerciale |
|---|---|---|
| Qwen (2.5/3) | Apache 2.0 | ✅ Sì |
| Gemma 3 | Gemma Terms of Use | ✅ Sì, con condizioni Google |
| DeepSeek-R1 Distill | MIT | ✅ Sì |
| Llama 3.3 | Llama Community License | ✅ Sì, con condizioni Meta |

**Obbligo:** cita sempre i modelli originali nei crediti.

## Dati e privacy

- I modelli locali (L3C) non inviano nulla all'esterno: **privacy totale**.
- Tutto ciò che passa per L3B esce dalla tua macchina: non inviare dati
  sensibili al cloud.
- OmniRoute gira al 100% in locale, zero telemetria; la sua cache resta
  sul tuo disco — svuotala se contiene dati sensibili.

## Licenza del progetto

TramaMind è rilasciato con licenza **MIT** (vedi [LICENSE](../LICENSE)).
Le licenze dei componenti di terze parti (OmniRoute, Ollama, Berd, modelli)
restano dei rispettivi titolari.
