# Avvio facile dell'app

Ho preparato tre modi semplici per avviare l'app locale.

## 1. App macOS senza terminale

Apri:

- `Trascrizione Locale.app`

Questa modalita e ormai da considerare legacy rispetto alla vera app standalone generata con PyInstaller.

Questa opzione:

- apre una vera finestra app nativa
- mostra la tua UI dentro la finestra, senza browser esterno
- non richiede di usare il terminale

Nota:

- essendo una app locale non firmata, al primo avvio macOS potrebbe chiederti conferma
- se succede, fai `tasto destro > Apri`
- dopo il primo avvio puoi anche trascinarla nel Dock

## 2. Doppio clic da Finder

Puoi anche usare:

- `Avvia Trascrizione.command`
- `Ferma Trascrizione.command`

Questa modalita apre Terminal, ma richiede solo doppio clic.

## 3. Manuale

Se vuoi ancora usare il terminale:

```bash
cd /percorso/del/progetto
./scripts/start_ui.sh
```

## File utili

- log server: `.ui_server.log`
- pid server: `.ui_server.pid`
