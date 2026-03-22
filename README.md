# Trascrizione Locale

App locale per trascrivere audio e video in italiano con:

- `faster-whisper` per la trascrizione
- `pyannote.audio` per la diarizzazione speaker opzionale
- preprocessing audio con `ffmpeg`
- revisione finale opzionale con OpenAI per punteggiatura e correzioni conservative
- UI desktop macOS e UI web locale

## Cosa contiene il repo

- `transcribe_local.py`: pipeline principale di trascrizione
- `ui_app.py`: UI web locale con upload, avanzamento e download output
- `desktop_window.py`: finestra desktop macOS basata su `pywebview`
- `app_runtime.py`: gestione dei percorsi runtime per sviluppo e app standalone
- `templates/` e `static/`: interfaccia HTML/CSS
- `scripts/build_standalone_app.sh`: build della `.app` standalone macOS
- `Trascrizione Locale.spec`: configurazione PyInstaller

## Cosa non viene versionato

Per tenere la repo pulita e portabile, non vengono salvati su GitHub:

- chiavi API e token locali (`.env.local`)
- virtualenv, cache e log
- upload e trascrizioni generate
- modelli scaricati localmente
- bundle `.app` e cartelle di build

Questo repo conserva quindi il progetto e i file necessari per ricostruire l'app, non i binari generati.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Avvio UI web:

```bash
python ui_app.py
```

Avvio pipeline CLI:

```bash
python transcribe_local.py input.m4a
```

## Build app standalone macOS

```bash
./scripts/build_standalone_app.sh
```

La build genera:

- `dist/Trascrizione Locale.app`
- `dist/Trascrizione-Locale-macOS-arm64.zip`

## Configurazione chiavi

Copia `.env.local.example` in `.env.local` e inserisci, se ti servono:

```env
OPENAI_API_KEY=la_tua_chiave
HF_TOKEN=il_tuo_token
```

## Documentazione

- [README_local_transcription.md](README_local_transcription.md)
- [README_web_ui.md](README_web_ui.md)
- [README_standalone.md](README_standalone.md)
- [README_launcher.md](README_launcher.md)

## Nota su GitHub

La `.app` standalone finale e piuttosto grande, quindi non e adatta a essere committata direttamente nel repository Git.  
Se in futuro vorrai distribuire i binari, la strada migliore sara usare GitHub Releases.
