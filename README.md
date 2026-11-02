# Trip YTD

Incolla un link YouTube e scarica l'audio in **MP3 320 kbps** o **WAV 16 bit / 44,1 kHz**,
oppure il **video nella massima qualità disponibile** (fino a 4K/8K, 60 fps, HDR) in MP4.
Per **macOS**, **Windows** e **Linux**.

## Scarica e installa

| Sistema | Installer |
|---|---|
| macOS 11 o successivo (Apple Silicon e Intel) | [Trip-YTD-macOS.pkg](https://github.com/maxtrip81/Trip-YTD/releases/latest/download/Trip-YTD-macOS.pkg) |
| Windows 10 e 11, 64 bit | [Trip-YTD-Windows-Setup.exe](https://github.com/maxtrip81/Trip-YTD/releases/latest/download/Trip-YTD-Windows-Setup.exe) |
| Linux 64 bit (x86_64 o ARM64) | [Trip-YTD-Linux.tar.gz](https://github.com/maxtrip81/Trip-YTD/releases/latest/download/Trip-YTD-Linux.tar.gz) |

Tutte le versioni: [Releases](https://github.com/maxtrip81/Trip-YTD/releases).

**macOS.** Apri `Trip-YTD-macOS.pkg` e segui l'installazione: Trip YTD finisce in Applicazioni,
con Python già incluso. L'installer non è firmato da uno sviluppatore Apple: se macOS lo blocca,
vai in Impostazioni di Sistema › Privacy e sicurezza e premi «Apri comunque».
Per disinstallare, trascina Trip YTD nel Cestino.

**Windows.** Apri `Trip-YTD-Windows-Setup.exe`. Se compare «Windows ha protetto il PC»:
Ulteriori informazioni › Esegui comunque. Non servono permessi di amministratore: Trip YTD si
installa per il tuo utente, con Python incluso, e compare nel menu Start (e, se vuoi, sul
desktop). Si disinstalla da Impostazioni › App, che rimuove anche i componenti scaricati.

**Linux.** Estrai l'archivio in una cartella stabile, apri un terminale lì ed esegui
`./trip-ytd`. Il primo avvio aggiunge «Trip YTD» al menu delle applicazioni. Serve Python 3.8
o successivo, presente in quasi tutte le distribuzioni dal 2019 in poi (Ubuntu 20.04,
Debian 10, Fedora 29, Linux Mint 20 o successive).

## Uso

1. Apri Trip YTD: la sua pagina si apre nel browser.
2. La prima volta premi **Installa componenti** (una volta sola).
3. Incolla il link (o trascinalo sulla pagina), scegli MP3, WAV o Video e premi **Scarica**.

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

## Creare gli installer

Ogni tag `vX.Y` avvia [GitHub Actions](.github/workflows/build.yml), che su macOS, Windows e
Linux crea gli installer, li installa, prova Trip YTD e pubblica la release.

A mano:
- **macOS e Linux**: su un Mac esegui `./build.sh`, che crea in `dist/` l'app, l'installer `.pkg`
  (con Python di [python-build-standalone](https://github.com/astral-sh/python-build-standalone))
  e l'archivio per Linux.
- **Windows**: con [Inno Setup 6](https://jrsoftware.org/isinfo.php) installato, esegui
  `powershell -File src\windows\build.ps1` (usa Python embeddable di python.org).
- Per provare senza installare: `python3 src/trip_ytd.py`.

Usa Trip YTD solo per contenuti che hai il diritto di scaricare.
