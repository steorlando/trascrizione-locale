# UI HTML locale per la trascrizione

Questa UI web gira in locale e usa direttamente la pipeline Python di trascrizione.

## File principali

- `ui_app.py`: server Flask locale
- `templates/index.html`: interfaccia HTML
- `static/styles.css`: stile della pagina
- `transcribe_local.py`: pipeline di trascrizione richiamata dalla UI

## Cosa fa

- permette di caricare file `mp3`, `m4a`, `wav`, `mp4`, `mov`, `mkv`, `aac`, `flac`, `ogg`
- esegue la trascrizione sul computer locale
- imposta di default `large-v3` come profilo di massima accuratezza
- permette di scegliere tra profilo accurato, veloce o modello manuale
- permette facoltativamente una revisione finale con OpenAI per punteggiatura e correzioni conservative
- mostra l’anteprima del testo nel browser
- permette di scaricare il `.txt`
- espone anche `.srt`, `.json` e, se attivi la revisione AI, il `.raw.txt` originale

## Installazione

Attiva l’ambiente virtuale e installa anche Flask:

```bash
cd /percorso/del/progetto
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Avvio

```bash
python ui_app.py
```

Poi apri:

```text
http://127.0.0.1:8000
```

## Revisione AI opzionale con OpenAI

L'app puo fare una revisione finale del testo trascritto per:

- aggiungere punteggiatura
- sistemare maiuscole e capoversi
- correggere solo errori molto evidenti

L'audio resta locale: OpenAI riceve solo il testo della trascrizione, non il file audio.

### Come configurare la chiave

1. Apri il file `.env.local`
2. Inserisci la chiave cosi:

```text
OPENAI_API_KEY=la_tua_chiave
```

3. Salva il file
4. Riavvia la UI se era gia aperta

### Come ottenere la API key

1. Vai alla pagina delle API key di OpenAI
2. Crea una nuova secret key
3. Copiala dentro `.env.local`

Modelli consigliati per la revisione:

- `gpt-4.1-mini`: default consigliato, buon equilibrio costo/qualita
- `gpt-4.1-nano`: piu economico, ma meno robusto sulle correzioni

## Note pratiche

- Per la miglior qualità in italiano, lascia `Massima accuratezza`, che usa `large-v3`.
- Se vuoi tempi più brevi, scegli `Più veloce` oppure usa `Scelta manuale`.
- Se attivi la revisione AI, il `.txt` finale viene corretto; il `.srt` resta basato sui segmenti grezzi con timestamp.
- Per uso semplice, lascia la diarizzazione disattivata.
- I memo vocali iPhone `.m4a` sono supportati.
- La trascrizione può richiedere tempo su CPU, soprattutto con `large-v3`.
- I file caricati vengono salvati in `web_uploads/` e gli output in `web_runs/`.
