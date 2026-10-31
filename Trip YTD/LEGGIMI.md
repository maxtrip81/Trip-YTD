# Trip YTD

Incolla un link YouTube e scarica l'audio in **MP3 320 kbps** o **WAV 16 bit / 44,1 kHz**.
Funziona su **macOS** e **Windows 10/11 (64 bit)**.

## Pacchetti (cartella `dist/`)

| File | Per |
|---|---|
| `Trip YTD.app` | Mac: pronta all'uso, trascinala in Applicazioni |
| `Trip YTD - macOS.zip` | Mac: la stessa app, da mandare ad altri |
| `Trip YTD - Windows.zip` | PC Windows: Python già incluso, nessuna installazione |

## Uso

**Mac.** Apri `Trip YTD.app`. Su un altro Mac, la prima volta: tasto destro › Apri
(l'app non è firmata da uno sviluppatore Apple).

**Windows.** Estrai tutto lo zip in una cartella stabile e fai doppio clic su
`Avvia Trip YTD`. Se compare "Windows ha protetto il PC": Ulteriori informazioni ›
Esegui comunque. Il primo avvio crea i collegamenti "Trip YTD" su Desktop e menu Start.

Poi, su entrambi:
1. La prima volta premi **Installa componenti** (una volta sola).
2. Incolla il link (o trascinalo sulla pagina), scegli MP3 o WAV e premi **Scarica**.

I file finiscono in `Download/Trip YTD` (si cambia con «Cambia» in fondo alla pagina).
Quando chiudi la pagina, Trip YTD si chiude da solo.

## Come funziona

- `src/trip_ytd.py`: server locale su `127.0.0.1:47320`, solo libreria standard di Python.
- `src/ui.html`: l'interfaccia, uguale sui due sistemi.
- Componenti scaricati al primo avvio, tutti verificati:

| | macOS (`~/Library/Application Support/Trip YTD/bin`) | Windows (`%LOCALAPPDATA%\Trip YTD\bin`) |
|---|---|---|
| yt-dlp | `yt-dlp_macos`, GitHub ufficiale, SHA-256 | `yt-dlp.exe`, GitHub ufficiale, SHA-256 |
| Deno (runtime JS per YouTube) | GitHub ufficiale, SHA-256 | GitHub ufficiale, SHA-256 |
| ffmpeg + ffprobe | evermeet.cx (linkato da ffmpeg.org), richiede Rosetta 2 | build del progetto yt-dlp, SHA-256 |
| Spazio | circa 130 MB da scaricare, 270 MB su disco | circa 160 MB da scaricare, 300 MB su disco |

- yt-dlp si aggiorna da solo ogni 2 giorni (o con «Aggiorna»).
- Si accettano solo link a un singolo video: playlist e canali vengono rifiutati.
- Registro: `trip_ytd.log` nella cartella dei componenti.

## Ricostruire i pacchetti

Dopo aver modificato i file in `src/`, su un Mac esegui `./build.sh`: ricrea tutto in `dist/`.
Per la versione Windows scarica (e verifica) Python 3.14 embeddable da python.org.
Per provare senza app: `python3 src/trip_ytd.py`.

Usa Trip YTD solo per audio che hai il diritto di scaricare.
