# Trascrizione locale avanzata in italiano

Questa soluzione crea una pipeline completamente locale per:

- preprocessing audio con `ffmpeg`
- trascrizione con `faster-whisper`
- diarizzazione speaker con `pyannote.audio`
- output in `.txt`, `.srt` e `.json`
- supporto a `--domain_prompt` per lessico tecnico, nomi propri e sigle

## Architettura proposta

La pipeline segue questi passaggi:

1. **Ingestione input**
   - accetta file audio o video: `mp3`, `m4a`, `wav`, `mp4`, `mov`, `mkv`, `flac`, `ogg`

2. **Preprocessing audio**
   - conversione in mono
   - resampling a 16 kHz
   - high-pass a 80 Hz per ridurre rumble e basse frequenze spurie
   - noise reduction con `afftdn`
   - loudness normalization con `loudnorm`

3. **Trascrizione**
   - usa `faster-whisper`
   - default su modello `large-v3`
   - lingua sempre forzata a italiano con `--language it`
   - supporta `--domain_prompt`, passato come `initial_prompt`

4. **Diarizzazione speaker**
   - usa `pyannote.audio`
   - assegna etichette come `SPEAKER_00`, `SPEAKER_01` ai segmenti
   - può usare `--num_speakers`, `--min_speakers`, `--max_speakers`

5. **Output**
   - `nomefile.txt`: testo leggibile
   - `nomefile.srt`: sottotitoli con timestamp
   - `nomefile.json`: metadati, segmenti, parole e speaker

## Perché questa scelta tecnica

### `faster-whisper`

È in genere più pratico del comando Whisper base perché:

- è più veloce
- gestisce bene modelli grandi
- espone opzioni utili per qualità e word timestamps
- è semplice da usare in Python

### `large-v3`

Vantaggi:

- accuratezza migliore rispetto ai modelli più piccoli
- migliore robustezza su audio rumoroso o lessico difficile
- utile per italiano, riunioni e lezioni

Svantaggi:

- più lento
- richiede più RAM

Se il Mac è limitato, conviene provare anche:

- `large-v3-turbo` se vuoi massimizzare la velocità
- `medium` se `large-v3` è troppo pesante
- `small` solo se ti serve risparmiare ancora più risorse

### Perché non `whisperX` come default

`whisperX` è molto utile, ma su macOS può risultare più fragile lato dipendenze e versioni.  
Qui la soluzione più stabile e pratica è:

- `faster-whisper` per trascrizione
- `pyannote.audio` per diarizzazione
- `ffmpeg` per preprocessing

## Installazione

## 1. Dipendenze di sistema

Assicurati di avere `ffmpeg`:

```bash
brew install ffmpeg
```

## 2. Ambiente Python

Consigliato creare un virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Nota importante sulla diarizzazione

La diarizzazione usa `pyannote.audio`, che è open source e gira in locale, ma i modelli vanno scaricati una prima volta da Hugging Face.

Passi consigliati:

1. crea un account Hugging Face
2. genera un access token
3. accetta i termini del modello `pyannote/speaker-diarization-3.1`
4. esporta il token:

```bash
export HF_TOKEN="il_tuo_token"
```

In alternativa puoi passarlo direttamente via CLI con `--hf_token`.

## Uso base

Esempio completo:

```bash
python transcribe_local.py input.m4a
```

Con output in cartella dedicata:

```bash
python transcribe_local.py input.m4a --output_dir output_transcripts
```

## Esempi utili

### Forzare italiano e usare un prompt di dominio

```bash
python transcribe_local.py input.m4a \
  --language it \
  --domain_prompt "sanità pubblica, epidemiologia, health economics, Tor Vergata, Sant’Egidio, Frontiers in Public Health"
```

### Scegliere il modello

```bash
python transcribe_local.py input.m4a --model large-v3
```

Oppure:

```bash
python transcribe_local.py input.m4a --model large-v3-turbo
```

### Disattivare diarizzazione

```bash
python transcribe_local.py input.m4a --no_diarization
```

### Disattivare preprocessing

```bash
python transcribe_local.py input.m4a --no_preprocess
```

### Limitare il numero di speaker

```bash
python transcribe_local.py riunione.mp3 --min_speakers 2 --max_speakers 4
```

### Specificare il numero esatto di speaker

```bash
python transcribe_local.py intervista.wav --num_speakers 2
```

## File prodotti

Dentro `output_transcripts/` troverai:

- `nomefile.preprocessed.wav`
- `nomefile.txt`
- `nomefile.srt`
- `nomefile.json`

## Struttura del JSON

Il JSON contiene:

- file di input
- file preprocessato
- metadati della trascrizione
- configurazione usata
- speaker turns
- segmenti con start/end/text/speaker
- parole con probabilità e timestamp, quando disponibili

## Errori comuni

### `ffmpeg` non trovato

Installa:

```bash
brew install ffmpeg
```

### Errore su `pyannote.audio`

Di solito dipende da:

- token HF mancante
- termini del modello non accettati
- installazione `torch`/`torchaudio` incompleta

Se vuoi eseguire solo la trascrizione:

```bash
python transcribe_local.py input.m4a --no_diarization
```

### Il modello `large-v3` è troppo lento

Prova:

```bash
python transcribe_local.py input.m4a --model large-v3-turbo
```

oppure:

```bash
python transcribe_local.py input.m4a --model medium
```

## Suggerimenti per migliorare accuratezza

- Usa `large-v3` quando possibile.
- Tieni `--language it` esplicito.
- Inserisci sempre un `--domain_prompt` ricco di nomi propri, sigle e termini tecnici.
- Se conosci il numero speaker, passa `--num_speakers`.
- Se l’audio è molto sporco, lascia il preprocessing attivo.
- Per audio già molto pulito, puoi provare `--no_preprocess`.
- Se i segmenti speaker non sono stabili, prova a restringere `--min_speakers` e `--max_speakers`.

## Suggerimenti per migliorare prestazioni

- Su CPU, `large-v3-turbo` e `medium` sono le alternative più pratiche se `large-v3` è troppo lento.
- Se hai poca RAM, usa `medium`.
- Su macOS senza CUDA, aspettati tempi maggiori rispetto a Linux/NVIDIA.
- Se vuoi solo testo rapido, usa `--no_diarization`.

## Nota sui modelli

- Per italiano e altri casi multilingua, il default consigliato resta `large-v3`.
- `large-v3-turbo` e `medium` sono opzioni più rapide ma meno accurate.
- `distil-large-v3` non è il preset consigliato qui perché la documentazione di Distil-Whisper lo presenta come checkpoint per speech recognition in inglese.

## Limiti realistici

- La diarizzazione su macOS CPU può essere lenta.
- `pyannote.audio` è molto utile ma più delicato da installare rispetto al resto della pipeline.
- Il `domain_prompt` aiuta, ma non garantisce il riconoscimento perfetto dei termini specialistici.
- Rumore forte, sovrapposizioni pesanti e microfoni scadenti restano casi difficili.
