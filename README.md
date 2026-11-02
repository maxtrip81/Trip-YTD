# Trip YTD

Incolla un link YouTube e scarica l'audio in **MP3 320 kbps** o **WAV 16 bit / 44,1 kHz**,
oppure il **video nella massima qualità disponibile** (fino a 4K/8K, 60 fps, HDR) in MP4.
Per **macOS**, **Windows** e **Linux**.

## Scarica

| Sistema | Pacchetto |
|---|---|
| macOS (Apple Silicon e Intel) | [Trip-YTD-macOS.zip](https://github.com/maxtrip81/Trip-YTD/releases/latest/download/Trip-YTD-macOS.zip) |
| Windows 10 e 11, 64 bit | [Trip-YTD-Windows.zip](https://github.com/maxtrip81/Trip-YTD/releases/latest/download/Trip-YTD-Windows.zip) |
| Linux 64 bit (x86_64 o ARM64) | [Trip-YTD-Linux.tar.gz](https://github.com/maxtrip81/Trip-YTD/releases/latest/download/Trip-YTD-Linux.tar.gz) |

Tutte le versioni: [Releases](https://github.com/maxtrip81/Trip-YTD/releases).

## Primo avvio

**macOS.** Estrai lo zip e trascina `Trip YTD.app` in Applicazioni. La prima volta aprila con
tasto destro › Apri, perché l'app non è firmata da uno sviluppatore Apple. Se macOS propone di
installare gli «Strumenti da riga di comando» (servono a Python), accetta e poi riapri l'app.

**Windows.** Estrai tutto lo zip in una cartella stabile e fai doppio clic su
`Avvia Trip YTD`. Se compare «Windows ha protetto il PC»: Ulteriori informazioni ›
Esegui comunque. Il primo avvio crea i collegamenti «Trip YTD» su Desktop e menu Start.
Python è già incluso.

**Linux.** Estrai l'archivio in una cartella stabile, apri un terminale lì ed esegui
`./trip-ytd`. Il primo avvio aggiunge «Trip YTD» al menu delle applicazioni. Serve Python 3.8
o successivo, presente in quasi tutte le distribuzioni dal 2019 in poi (Ubuntu 20.04,
Debian 10, Fedora 29, Linux Mint 20 o successive).

Poi, su tutti i sistemi:
1. La prima volta premi **Installa componenti** (una volta sola).
2. Incolla il link (o trascinalo sulla pagina), scegli MP3, WAV o Video e premi **Scarica**.

I file finiscono nella cartella Download (Scaricati su Linux in italiano), in `Trip YTD`.
Si cambia con «Cambia» in fondo alla pagina. Quando chiudi la pagina, Trip YTD si chiude da solo.

## Video

Trip YTD sceglie la risoluzione più alta, poi gli fps più alti e l'HDR, e unisce il video
all'audio migliore in un file MP4 con copertina e capitoli. A parità di qualità preferisce VP9
ad AV1, che molti computer non decodificano in hardware.

Sopra il 1080p YouTube usa i codec VP9 o AV1, che QuickTime non riproduce:
- su Mac usa [VLC](https://www.videolan.org) o [IINA](https://iina.io);
- su Windows Lettore multimediale (con le estensioni VP9/AV1 di Microsoft) o VLC;
- su Linux VLC, mpv, Celluloid o i lettori video di GNOME e KDE.

## Come funziona

- `src/trip_ytd.py`: server locale su `127.0.0.1:47320`, solo libreria standard di Python.
- `src/ui.html`: l'interfaccia nel browser, uguale su tutti i sistemi.
- Componenti scaricati al primo avvio dalle fonti ufficiali, tutti verificati:

| | macOS | Windows | Linux |
|---|---|---|---|
| Cartella | `~/Library/Application Support/Trip YTD` | `%LOCALAPPDATA%\Trip YTD` | `~/.local/share/trip-ytd` |
| yt-dlp | GitHub ufficiale, SHA-256 | GitHub ufficiale, SHA-256 | GitHub ufficiale, SHA-256 |
| Deno (runtime JS per YouTube) | GitHub ufficiale, SHA-256 | GitHub ufficiale, SHA-256 | GitHub ufficiale, SHA-256 |
| ffmpeg + ffprobe | evermeet.cx (indicato da ffmpeg.org), richiede Rosetta 2 | build del progetto yt-dlp, SHA-256 | build del progetto yt-dlp, SHA-256 |
| Spazio | 130 MB da scaricare, 270 MB su disco | 160 MB da scaricare, 300 MB su disco | 240 MB da scaricare, 470 MB su disco |

- yt-dlp si aggiorna da solo ogni 2 giorni (o con «Aggiorna»).
- Si accettano solo link a un singolo video: playlist e canali vengono rifiutati.
- Registro: `trip_ytd.log` nella cartella dei componenti.

## Ricostruire i pacchetti

Dopo aver modificato i file in `src/`, su un Mac esegui `./build.sh`: ricrea tutto in `dist/`.
Per la versione Windows scarica (e verifica) Python 3.14 embeddable da python.org.
Per provare senza pacchetti: `python3 src/trip_ytd.py`.

Usa Trip YTD solo per contenuti che hai il diritto di scaricare.
