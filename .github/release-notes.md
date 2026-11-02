Incolla un link YouTube e scarica l'audio in **MP3 320 kbps** o **WAV 16 bit / 44,1 kHz**, oppure il **video nella massima qualità disponibile** (fino a 4K/8K, 60 fps, HDR) in MP4.

## Scarica e installa

| Sistema | Installer |
|---|---|
| macOS 11 o successivo (Apple Silicon e Intel) | [Trip-YTD-macOS.pkg](https://github.com/maxtrip81/Trip-YTD/releases/download/@TAG@/Trip-YTD-macOS.pkg) |
| Windows 10 e 11, 64 bit | [Trip-YTD-Windows-Setup.exe](https://github.com/maxtrip81/Trip-YTD/releases/download/@TAG@/Trip-YTD-Windows-Setup.exe) |
| Linux 64 bit (x86_64 o ARM64) | [Trip-YTD-Linux.tar.gz](https://github.com/maxtrip81/Trip-YTD/releases/download/@TAG@/Trip-YTD-Linux.tar.gz) |

**macOS.** Apri `Trip-YTD-macOS.pkg` e segui l'installazione. L'installer non è firmato da uno sviluppatore Apple: se macOS lo blocca, vai in Impostazioni di Sistema › Privacy e sicurezza e premi «Apri comunque». Poi apri Trip YTD da Applicazioni o Launchpad. Python è già incluso.

**Windows.** Apri `Trip-YTD-Windows-Setup.exe`. Se compare «Windows ha protetto il PC», premi Ulteriori informazioni › Esegui comunque. Non servono permessi di amministratore. Trip YTD compare nel menu Start (e, se vuoi, sul desktop) e si disinstalla da Impostazioni › App.

**Linux.** Estrai l'archivio, apri un terminale nella cartella ed esegui `./trip-ytd`: Trip YTD compare nel menu delle applicazioni. Serve Python 3.8 o successivo.

Al primo avvio premi **Installa componenti**: yt-dlp, Deno e ffmpeg vengono scaricati dalle fonti ufficiali e verificati.

Sopra il 1080p YouTube usa i codec VP9 o AV1: per i video usa VLC, IINA (Mac) o il lettore del sistema con i codec installati.

Usa Trip YTD solo per contenuti che hai il diritto di scaricare.
