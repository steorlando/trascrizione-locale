# Trascrizione Locale Standalone

Questo progetto puo essere compilato come vera app macOS standalone.

Nel repository Git viene salvato il codice e la configurazione di build, non il bundle `.app` finale.

La vecchia app-launcher basata su Terminale e browser puo restare come fallback locale, ma la direzione consigliata e la build standalone.

## Come si usa

1. Costruisci la app con lo script di build.
2. Apri `Trascrizione Locale.app`.
2. Si apre direttamente la finestra dell'app.
3. Carica il file audio/video e avvia la trascrizione.

## Dove salva i dati

La app standalone non scrive dentro il bundle `.app`.

Su macOS usa queste cartelle utente:

- Config e token:
  - `~/Library/Application Support/Trascrizione Locale/.env.local`
- Esempio di config:
  - `~/Library/Application Support/Trascrizione Locale/.env.local.example`
- Upload temporanei:
  - `~/Library/Application Support/Trascrizione Locale/web_uploads/`
- Output finali:
  - `~/Library/Application Support/Trascrizione Locale/web_runs/`
- Cache:
  - `~/Library/Caches/Trascrizione Locale/`

## OpenAI e Hugging Face

Se vuoi usare revisione AI e diarizzazione, scrivi le chiavi qui:

```env
OPENAI_API_KEY=la_tua_chiave
HF_TOKEN=il_tuo_token
```

File da modificare:

- `~/Library/Application Support/Trascrizione Locale/.env.local`

## Come ricostruire la app

Script di build:

- `scripts/build_standalone_app.sh`

Comando:

```bash
cd /percorso/del/progetto
./scripts/build_standalone_app.sh
```

Output della build:

- app bundle generato dalla build: `dist/Trascrizione Locale.app`
- archivio zip: `dist/Trascrizione-Locale-macOS-arm64.zip`

## Uso su altri Mac

L'archivio zip pronto da copiare e:

- `dist/Trascrizione-Locale-macOS-arm64.zip`

Note importanti:

- questa build e per Mac Apple Silicon (`arm64`)
- su un altro Mac Apple Silicon puoi copiare lo zip, estrarlo e aprire la app
- al primo avvio macOS potrebbe richiedere `tasto destro > Apri`
- il primo download dei modelli Whisper o pyannote puo richiedere internet, se non sono gia in cache

Per una distribuzione ancora piu pulita a terzi, il passo successivo sarebbe la firma con certificato Apple Developer e la notarizzazione.
