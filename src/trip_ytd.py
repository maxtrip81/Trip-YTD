#!/usr/bin/env python3
"""Trip YTD: incolla un link YouTube e scarica l'audio in MP3 320k o WAV,
oppure il video nella massima qualità disponibile.

Server locale (solo libreria standard di Python) con interfaccia nel browser,
per macOS, Windows e Linux. Alla prima apertura scarica i componenti esterni
(yt-dlp, Deno, ffmpeg, ffprobe) dalle loro fonti ufficiali nella cartella
dati dell'app: ~/Library/Application Support/Trip YTD su macOS,
%LOCALAPPDATA%\\Trip YTD su Windows, ~/.local/share/trip-ytd su Linux.
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "Trip YTD"
VERSION = "1.4"
HOST = "127.0.0.1"
PORT = 47320
URL = "http://%s:%d/" % (HOST, PORT)
USER_AGENT = "%s/%s" % (APP_NAME, VERSION)

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = not (IS_WIN or IS_MAC)

HERE = Path(__file__).resolve().parent
if IS_WIN:
    SUPPORT = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
elif IS_MAC:
    SUPPORT = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    XDG_DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    SUPPORT = XDG_DATA / "trip-ytd"
BIN = SUPPORT / "bin"
WORK = SUPPORT / "work"
CONFIG_FILE = SUPPORT / "config.json"
LOG_FILE = SUPPORT / "trip_ytd.log"

YTDLP = BIN / ("yt-dlp.exe" if IS_WIN else "yt-dlp")

IDLE_TIMEOUT = 15 * 60       # chiude il server dopo 15 minuti senza la pagina aperta
BYE_GRACE = 20               # dopo la chiusura della pagina attende un eventuale ricaricamento
UPDATE_EVERY = 2 * 24 * 3600  # controllo aggiornamenti di yt-dlp ogni 2 giorni

# Su Windows i programmi a riga di comando non devono aprire finestre di console.
NO_WINDOW = {"creationflags": 0x08000000} if IS_WIN else {}  # CREATE_NO_WINDOW

YTDLP_RELEASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
DENO_RELEASE = "https://github.com/denoland/deno/releases/latest/download/"
# macOS: build statiche indicate su ffmpeg.org/download.html
EVERMEET_INFO = "https://evermeet.cx/ffmpeg/info/%s/release"
# Windows e Linux: build curate dal progetto yt-dlp (su Linux con le librerie incluse, richiedono glibc 2.28)
FFMPEG_BUILDS = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
FFMPEG_WIN_ZIP = "ffmpeg-master-latest-win64-gpl-shared.zip"
# Linux: architettura → (yt-dlp, Deno, ffmpeg)
LINUX_ASSETS = {
    "x86_64": ("yt-dlp_linux", "x86_64-unknown-linux-gnu", "ffmpeg-master-latest-linux64-gpl.tar.xz"),
    "aarch64": ("yt-dlp_linux_aarch64", "aarch64-unknown-linux-gnu", "ffmpeg-master-latest-linuxarm64-gpl.tar.xz"),
}
LINUX_ASSETS["amd64"], LINUX_ASSETS["arm64"] = LINUX_ASSETS["x86_64"], LINUX_ASSETS["aarch64"]

AUDIO_ARGS = ["-f", "bestaudio/best", "-x", "--postprocessor-args", "ExtractAudio:-ar 44100"]
COVER_ARGS = ["--embed-thumbnail", "--convert-thumbnails", "jpg"]

FORMATS = {
    "mp3": {
        "label": "MP3 320k",
        "exts": ("mp3",),
        "args": AUDIO_ARGS + ["--audio-format", "mp3", "--audio-quality", "320K"] + COVER_ARGS,
    },
    "wav": {
        "label": "WAV",
        "exts": ("wav",),
        "args": AUDIO_ARGS + ["--audio-format", "wav"],
    },
    # Massima qualità: prima la risoluzione, poi fps e HDR. A parità di queste preferisce
    # VP9 ad AV1, che molti computer non decodificano in hardware. Sempre in un file MP4.
    "video": {
        "label": "Video",
        "video": True,
        "exts": ("mp4", "mkv", "webm"),
        "args": ["-f", "bv*+ba/b", "-S", "res,fps,hdr:12,vcodec:vp9",
                 "--merge-output-format", "mp4", "--embed-chapters"] + COVER_ARGS,
    },
}

FRIENDLY_ERRORS = [
    ("private video", "Il video è privato."),
    ("members-only", "Il video è riservato agli abbonati del canale."),
    ("confirm your age", "Il video ha limiti di età: YouTube richiede l'accesso con un account."),
    ("not a bot", "YouTube chiede di confermare che non sei un bot. Riprova tra qualche minuto."),
    ("video unavailable", "Il video non è disponibile (rimosso o bloccato nel tuo Paese)."),
    ("video is unavailable", "Il video non esiste o non è più disponibile."),
    ("this live event will begin", "La diretta non è ancora iniziata."),
    ("requested format is not available", "Il formato richiesto non è disponibile per questo video."),
    ("no space left", "Spazio su disco esaurito."),
    ("postprocessing:", "ffmpeg non è riuscito a elaborare il file."),
    ("http error 403", "YouTube ha rifiutato il download. Prova con «Aggiorna» in fondo alla pagina."),
    ("bad cpu type", "ffmpeg richiede Rosetta 2. Nel Terminale esegui: softwareupdate --install-rosetta"),
    ("unable to download webpage", "Connessione a YouTube non riuscita. Controlla la rete."),
    ("getaddrinfo", "Connessione a internet assente."),
    ("timed out", "Connessione a YouTube troppo lenta o interrotta."),
]

log = logging.getLogger("trip_ytd")


# ---------------------------------------------------------------------------
# Utilità


def video_id(text):
    """Restituisce l'ID del video se `text` è il link di un singolo video YouTube."""
    s = (text or "").strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I):
        s = "https://" + s
    try:
        u = urllib.parse.urlparse(s)
    except ValueError:
        return None
    host = (u.hostname or "").lower()
    vid = None
    if host in ("youtu.be", "www.youtu.be"):
        vid = u.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com") or host.endswith((".youtube.com", ".youtube-nocookie.com")):
        if u.path.rstrip("/") == "/watch":
            vid = urllib.parse.parse_qs(u.query).get("v", [None])[0]
        else:
            m = re.match(r"^/(?:shorts|live|embed|v)/([^/?#]+)", u.path)
            vid = m.group(1) if m else None
    if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        return vid
    return None


def is_youtube_host(text):
    s = (text or "").strip()
    return bool(re.match(r"^(?:[a-z]+://)?(?:[a-z0-9-]+\.)*(?:youtube\.com|youtu\.be|youtube-nocookie\.com)(?:[/:?#]|$)", s, re.I))


def friendly_error(raw):
    low = (raw or "").lower()
    for needle, msg in FRIENDLY_ERRORS:
        if needle in low:
            return msg
    return "Download non riuscito."


def to_number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def quality_label(width, height, fps, dynamic_range):
    """Es. «1080p60», «4K HDR»: la risoluzione è il lato corto (vale anche per gli Shorts verticali)."""
    side = min(width, height) if width and height else height
    if not side:
        return ""
    label = "8K" if side >= 4320 else "4K" if side >= 2160 else "%dp" % side
    if fps and fps > 30:
        label += "%d" % round(fps)
    if dynamic_range and dynamic_range not in ("SDR", "NA"):
        label += " HDR"
    return label


def downloads_dir():
    if IS_WIN:
        # la cartella Download può essere spostata (es. su OneDrive): la chiede a Windows
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            u = uuid.UUID("374DE290-123F-4565-9164-39C4925E467B")  # FOLDERID_Downloads
            guid = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
                path = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
                return Path(path)
        except Exception:
            pass
    elif IS_LINUX:
        # la cartella Download ha il nome nella lingua del sistema (es. ~/Scaricati)
        try:
            r = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5)
            path = r.stdout.strip()
            if r.returncode == 0 and path and Path(path) != Path.home():
                return Path(path)
        except (OSError, subprocess.SubprocessError):
            pass
        dirs = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "user-dirs.dirs"
        try:
            m = re.search(r'^XDG_DOWNLOAD_DIR="([^"]+)"', dirs.read_text(encoding="utf-8"), re.M)
            if m:
                return Path(m.group(1).replace("$HOME", str(Path.home())))
        except OSError:
            pass
    return Path.home() / "Downloads"


DEFAULT_OUT = downloads_dir() / APP_NAME


def human_path(path):
    if IS_WIN:
        return str(path)
    home = str(Path.home())
    p = str(path)
    return "~" + p[len(home):] if p.startswith(home) else p


def tool_env():
    env = dict(os.environ)
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "/usr/bin:/bin")
    env.setdefault("LANG", "en_US.UTF-8")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def ps_str(s):
    """Stringa PowerShell tra apici singoli."""
    return "'" + str(s).replace("'", "''") + "'"


def run_powershell(script, timeout=120):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass",
                           "-EncodedCommand", encoded], capture_output=True, timeout=timeout, **NO_WINDOW)


# ---------------------------------------------------------------------------
# Download dei componenti

# Su macOS i download passano da curl di sistema: alcuni mirror richiedono TLS 1.3,
# che il Python di sistema (LibreSSL 2.8) non supporta. Su Windows e Linux basta urllib.
CURL = ["/usr/bin/curl", "-fL", "--retry", "2", "--connect-timeout", "20", "-A", USER_AGENT]


def download_error(url, reason):
    return RuntimeError("Download non riuscito da %s: %s" % (urllib.parse.urlparse(url).hostname, reason))


def curl_error(stderr, url):
    lines = [l.strip() for l in stderr.decode(errors="replace").replace("\r", "\n").splitlines() if "curl:" in l]
    return download_error(url, lines[-1] if lines else "errore di rete")


def urlopen(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(req, timeout=60)
    except OSError as e:
        raise download_error(url, getattr(e, "reason", None) or e)


def http_text(url):
    if not IS_MAC:
        with urlopen(url) as r:
            return r.read().decode()
    r = subprocess.run(CURL + ["-sS", url], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise curl_error(r.stderr, url)
    return r.stdout.decode()


def fetch(url, dest, on_progress):
    tmp = dest.with_name(dest.name + ".part")
    try:
        if IS_MAC:
            _fetch_curl(url, tmp, on_progress)
        else:
            _fetch_urllib(url, tmp, on_progress)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    tmp.replace(dest)
    return dest


def _fetch_curl(url, tmp, on_progress):
    proc = subprocess.Popen(CURL + ["--progress-bar", "-o", str(tmp), url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    tail = b""
    while True:
        chunk = os.read(proc.stderr.fileno(), 512)
        if not chunk:
            break
        tail = (tail + chunk)[-1024:]
        pct = re.findall(rb"(\d{1,3}(?:\.\d)?)%", tail)
        if pct:
            on_progress(min(float(pct[-1]) / 100, 0.99))
    if proc.wait() != 0:
        raise curl_error(tail, url)


def _fetch_urllib(url, tmp, on_progress):
    with urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 18)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                on_progress(min(done / total, 0.99))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(path, expected, what):
    if not expected or sha256(path) != expected.lower():
        path.unlink()
        raise RuntimeError("Verifica di %s non riuscita (checksum diverso)." % what)


def checksum_for(sums_text, name):
    return next((l.split()[0] for l in sums_text.splitlines() if l.strip().endswith(" " + name)), None)


def make_executable(path):
    path.chmod(0o755)


def extract_members(archive, wanted, dest_dir):
    """Estrae in dest_dir (senza sottocartelle) i file dell'archivio zip o tar il cui nome soddisfa wanted(nome)."""
    found = []
    if archive.name.endswith((".tar.xz", ".tar.gz")):
        with tarfile.open(archive) as t:
            for member in t:
                base = member.name.rstrip("/").split("/")[-1]
                if member.isfile() and wanted(base):
                    _write_member(t.extractfile(member), dest_dir / base)
                    found.append(base)
    else:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                base = info.filename.rstrip("/").split("/")[-1]
                if not info.is_dir() and wanted(base):
                    _write_member(z.open(info), dest_dir / base)
                    found.append(base)
    return found


def _write_member(src, dest):
    tmp = dest.with_name(dest.name + ".part")
    with src, open(tmp, "wb") as out:
        shutil.copyfileobj(src, out)
    tmp.replace(dest)
    make_executable(dest)


def install_ytdlp(asset, filename):
    def install(dest_dir, progress):
        expected = checksum_for(http_text(YTDLP_RELEASE + "SHA2-256SUMS"), asset)
        tmp = fetch(YTDLP_RELEASE + asset, dest_dir / asset, progress)
        verify(tmp, expected, "yt-dlp")
        make_executable(tmp)
        tmp.replace(dest_dir / filename)
    return install


def install_deno(target):
    def install(dest_dir, progress):
        name = "deno-%s.zip" % target
        # su macOS il file è nel formato di sha256sum, su Windows in quello di PowerShell
        m = re.search(r"\b[0-9a-fA-F]{64}\b", http_text(DENO_RELEASE + name + ".sha256sum"))
        expected = m.group(0) if m else None
        tmp = fetch(DENO_RELEASE + name, dest_dir / name, progress)
        try:
            verify(tmp, expected, "Deno")
            extract_members(tmp, lambda base: base in ("deno", "deno.exe"), dest_dir)
        finally:
            if tmp.exists():
                tmp.unlink()
    return install


def install_evermeet(tool):
    def install(dest_dir, progress):
        meta = json.loads(http_text(EVERMEET_INFO % tool))["download"]["zip"]
        tmp = fetch(meta["url"], dest_dir / ("%s.zip" % tool), progress)
        try:
            if tmp.stat().st_size != int(meta["size"]):
                raise RuntimeError("Download di %s incompleto." % tool)
            extract_members(tmp, lambda base: base == tool, dest_dir)
        finally:
            tmp.unlink()
    return install


def install_ffmpeg_builds(archive, wanted):
    def install(dest_dir, progress):
        expected = checksum_for(http_text(FFMPEG_BUILDS + "checksums.sha256"), archive)
        tmp = fetch(FFMPEG_BUILDS + archive, dest_dir / archive, progress)
        try:
            verify(tmp, expected, "ffmpeg")
            extract_members(tmp, wanted, dest_dir)
        finally:
            if tmp.exists():
                tmp.unlink()
    return install


def mac_components():
    arch = "aarch64" if platform.machine() == "arm64" else "x86_64"
    return [
        {"id": "yt-dlp", "label": "yt-dlp", "desc": "motore di download", "files": ["yt-dlp"],
         "install": install_ytdlp("yt-dlp_macos", "yt-dlp")},
        {"id": "deno", "label": "Deno", "desc": "runtime JavaScript richiesto da YouTube", "files": ["deno"],
         "install": install_deno(arch + "-apple-darwin")},
        {"id": "ffmpeg", "label": "ffmpeg", "desc": "conversione audio e unione audio/video", "files": ["ffmpeg"],
         "install": install_evermeet("ffmpeg")},
        {"id": "ffprobe", "label": "ffprobe", "desc": "analisi dei file audio e video", "files": ["ffprobe"],
         "install": install_evermeet("ffprobe")},
    ]


def windows_components():
    return [
        {"id": "yt-dlp", "label": "yt-dlp", "desc": "motore di download", "files": ["yt-dlp.exe"],
         "install": install_ytdlp("yt-dlp.exe", "yt-dlp.exe")},
        {"id": "deno", "label": "Deno", "desc": "runtime JavaScript richiesto da YouTube", "files": ["deno.exe"],
         "install": install_deno("x86_64-pc-windows-msvc")},
        # build "shared": servono anche le DLL accanto agli eseguibili
        {"id": "ffmpeg", "label": "ffmpeg", "desc": "conversione audio e unione audio/video",
         "files": ["ffmpeg.exe", "ffprobe.exe"],
         "install": install_ffmpeg_builds(
             FFMPEG_WIN_ZIP, lambda base: base in ("ffmpeg.exe", "ffprobe.exe") or base.endswith(".dll"))},
    ]


def linux_components():
    ytdlp, deno, ffmpeg = LINUX_ASSETS.get(platform.machine().lower(), LINUX_ASSETS["x86_64"])
    return [
        {"id": "yt-dlp", "label": "yt-dlp", "desc": "motore di download", "files": ["yt-dlp"],
         "install": install_ytdlp(ytdlp, "yt-dlp")},
        {"id": "deno", "label": "Deno", "desc": "runtime JavaScript richiesto da YouTube", "files": ["deno"],
         "install": install_deno(deno)},
        {"id": "ffmpeg", "label": "ffmpeg", "desc": "conversione audio e unione audio/video",
         "files": ["ffmpeg", "ffprobe"],
         "install": install_ffmpeg_builds(ffmpeg, lambda base: base in ("ffmpeg", "ffprobe"))},
    ]


if IS_WIN:
    COMPONENTS, SETUP_SIZE = windows_components(), "circa 160 MB da scaricare, 300 MB su disco"
elif IS_MAC:
    COMPONENTS, SETUP_SIZE = mac_components(), "circa 130 MB da scaricare, 270 MB su disco"
else:
    COMPONENTS, SETUP_SIZE = linux_components(), "circa 240 MB da scaricare, 470 MB su disco"


def component_installed(c):
    return all(os.access(str(BIN / f), os.X_OK) for f in c["files"])


def ytdlp_version():
    try:
        r = subprocess.run([str(YTDLP), "--version"], capture_output=True, text=True, timeout=60,
                           env=tool_env(), **NO_WINDOW)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def needs_rosetta():
    if not IS_MAC or platform.machine() != "arm64":
        return False
    try:
        return subprocess.run(["/usr/bin/arch", "-x86_64", "/usr/bin/true"], capture_output=True).returncode != 0
    except OSError:
        return True


def setup_blocker():
    """Il motivo per cui i componenti non si possono installare su questo computer, oppure None."""
    if IS_LINUX and platform.machine().lower() not in LINUX_ASSETS:
        return ("Trip YTD per Linux funziona su computer a 64 bit (x86_64 o ARM64), "
                "questo è %s." % (platform.machine() or "sconosciuto"))
    if needs_rosetta():
        return ("ffmpeg per macOS richiede Rosetta 2. Apri il Terminale, esegui "
                "«softwareupdate --install-rosetta» e poi riprova.")
    return None


# ---------------------------------------------------------------------------
# Azioni sul sistema (Finder / Esplora file / file manager, browser, collegamenti)


def xdg_open(target):
    subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_browser():
    if IS_MAC:
        subprocess.Popen(["/usr/bin/open", URL])
    else:
        webbrowser.open(URL)


def open_folder(path):
    if IS_WIN:
        os.startfile(str(path))
    elif IS_MAC:
        subprocess.Popen(["/usr/bin/open", str(path)])
    else:
        xdg_open(path)


def reveal_file(path):
    if IS_WIN:
        subprocess.Popen('explorer /select,"%s"' % path)
    elif IS_MAC:
        subprocess.Popen(["/usr/bin/open", "-R", path])
    else:
        # chiede al file manager (Nautilus, Dolphin, Nemo, Thunar…) di selezionare il file
        try:
            r = subprocess.run(
                ["dbus-send", "--session", "--print-reply", "--dest=org.freedesktop.FileManager1",
                 "--type=method_call", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1.ShowItems",
                 "array:string:" + Path(path).as_uri(), "string:"],
                capture_output=True, timeout=10)
            if r.returncode == 0:
                return
        except (OSError, subprocess.SubprocessError):
            pass
        xdg_open(os.path.dirname(path))


def play_file(path, video=False):
    if IS_WIN:
        os.startfile(path)
    elif IS_LINUX:
        xdg_open(path)
    elif video:
        # il lettore predefinito: QuickTime non riproduce VP9/AV1, VLC o IINA sì
        subprocess.Popen(["/usr/bin/open", path])
    else:
        subprocess.Popen(["/usr/bin/open", "-a", "QuickTime Player", path])


def choose_folder_dialog(start):
    """Mostra la finestra di scelta cartella; None se annullata."""
    prompt = "Dove vuoi salvare i file di Trip YTD?"
    if IS_WIN:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms\n"
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\n"
            "$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}\n"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog\n"
            "$d.Description = %s\n"
            "$d.SelectedPath = %s\n"
            "if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { $d.SelectedPath }\n"
            "$owner.Dispose()\n"
        ) % (ps_str(prompt), ps_str(start))
        r = run_powershell(script, timeout=None)
        chosen = r.stdout.decode("utf-8", "replace").strip().lstrip("﻿")
    elif IS_MAC:
        script = 'POSIX path of (choose folder with prompt "%s" default location (POSIX file "%s"))' % (
            prompt, str(start).replace("\\", "\\\\").replace('"', '\\"'))
        r = subprocess.run(["/usr/bin/osascript", "-e", "activate", "-e", script], capture_output=True, text=True)
        chosen = r.stdout.strip()
    else:
        if shutil.which("zenity"):
            cmd = ["zenity", "--file-selection", "--directory", "--title", prompt, "--filename", str(start) + "/"]
        elif shutil.which("kdialog"):
            cmd = ["kdialog", "--getexistingdirectory", str(start), "--title", prompt]
        else:
            cmd = [sys.executable, "-c", TK_FOLDER_PICKER, prompt, str(start)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        chosen = r.stdout.strip()
        if r.returncode != 0 and "tkinter" in r.stderr:
            raise RuntimeError("Per scegliere la cartella installa zenity "
                               "(per esempio: sudo apt install zenity) e riprova.")
    if r.returncode != 0 or not chosen:
        return None
    return chosen.rstrip("/\\") or chosen


TK_FOLDER_PICKER = (
    "import sys, tkinter, tkinter.filedialog as fd\n"
    "root = tkinter.Tk(); root.withdraw()\n"
    "print(fd.askdirectory(title=sys.argv[1], initialdir=sys.argv[2], mustexist=True) or '')\n"
)


def desktop_exec_arg(arg):
    """Argomento tra virgolette per la chiave Exec di un file .desktop."""
    quoted = '"%s"' % re.sub(r'([\\"`$])', r'\\\1', str(arg))
    return quoted.replace("\\", "\\\\").replace("%", "%%")


def create_linux_shortcut():
    """Aggiunge «Trip YTD» al menu delle applicazioni."""
    apps = XDG_DATA / "applications"
    entry = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Trip YTD",
        "Comment=Audio e video da YouTube",
        "Exec=%s %s" % (desktop_exec_arg(sys.executable), desktop_exec_arg(HERE / "trip_ytd.py")),
        "Icon=" + str(HERE / "icon.png").replace("\\", "\\\\"),
        "Terminal=false",
        "Categories=AudioVideo;Network;",
        "Keywords=YouTube;MP3;WAV;video;download;",
        "StartupNotify=false",
        "",
    ])
    try:
        apps.mkdir(parents=True, exist_ok=True)
        tmp = apps / "trip-ytd.desktop.part"
        tmp.write_text(entry, encoding="utf-8")
        tmp.chmod(0o755)
        tmp.replace(apps / "trip-ytd.desktop")
    except OSError as e:
        log.warning("voce del menu non creata: %s", e)


# ---------------------------------------------------------------------------
# Download


class Job:
    def __init__(self, url, vid, fmt, outdir):
        self.id = uuid.uuid4().hex[:10]
        self.url = url
        self.vid = vid
        self.fmt = fmt
        self.outdir = outdir
        self.status = "starting"  # starting → downloading → converting → done | error | cancelled
        self.percent = 0.0
        self.speed = ""
        self.eta = ""
        self.title = ""
        self.quality = ""
        # un video arriva in due parti (video e audio) che yt-dlp scarica una dopo l'altra
        self.parts = 1
        self.parts_done = 0
        self.bytes_done = 0
        self.size_estimate = 0
        self.filepath = None
        self.size = 0
        self.error = None
        self.detail = None
        self.proc = None
        self.cancelled = False
        self.created = time.time()
        self.lines = deque(maxlen=80)

    @property
    def active(self):
        return self.status in ("starting", "downloading", "converting")

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "vid": self.vid,
            "format": self.fmt,
            "format_label": " ".join(filter(None, (FORMATS[self.fmt]["label"], self.quality))),
            "status": self.status,
            "percent": round(self.percent, 1),
            "speed": self.speed,
            "eta": self.eta,
            "title": self.title,
            "filename": os.path.basename(self.filepath) if self.filepath else None,
            "size": self.size,
            "error": self.error,
            "detail": self.detail,
        }

    def command(self):
        work = WORK / self.id
        cmd = [
            str(YTDLP), "--ignore-config", "--no-playlist", "--no-simulate",
            "--newline", "--progress",
            "--progress-template",
            "download:TRIP_PROG %(progress.status)s|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s"
            "|%(progress.downloaded_bytes)s|%(progress.total_bytes,progress.total_bytes_estimate)s",
            "--print", "video:TRIP_TITLE %(title)s",
            "--print", "video:TRIP_INFO %(format_id)s|%(filesize,filesize_approx)s"
                       "|%(width)s|%(height)s|%(fps)s|%(dynamic_range)s",
            "--print", "after_move:TRIP_FILE %(filepath)s",
            "--ffmpeg-location", str(BIN),
            "--embed-metadata", "--no-mtime",
            "--windows-filenames", "--trim-filenames", "160",
            "-P", "home:" + str(self.outdir),
            "-P", "temp:" + str(work),
            "-o", "%(title)s.%(ext)s",
        ]
        if IS_WIN:
            # l'output di yt-dlp.exe altrimenti usa la codepage della console
            cmd += ["--encoding", "utf-8"]
        cmd += FORMATS[self.fmt]["args"]
        cmd += ["--", "https://www.youtube.com/watch?v=" + self.vid]
        return cmd

    def run(self):
        work = WORK / self.id
        code = None
        try:
            work.mkdir(parents=True, exist_ok=True)
            if self.cancelled:
                return
            cmd = self.command()
            log.info("job %s: %s", self.id, " ".join(cmd))
            extra = NO_WINDOW if IS_WIN else {"start_new_session": True}
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=tool_env(),
                text=True, encoding="utf-8", errors="replace", bufsize=1, **extra,
            )
            for line in self.proc.stdout:
                self._parse(line.rstrip("\n"))
            code = self.proc.wait()
        except OSError as e:
            self.detail = str(e)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            self._finish(code)

    def _parse(self, line):
        self.lines.append(line)
        if line.startswith("TRIP_PROG "):
            parts = (line[len("TRIP_PROG "):].split("|") + [""] * 6)[:6]
            status, pct, speed, eta, done, total = (p.strip() for p in parts)
            pct = to_number(pct.rstrip("%"))
            done, total = to_number(done) or 0, to_number(total) or 0
            self.speed = "" if speed in ("N/A", "NA", "Unknown", "Unknown B/s") else speed
            self.eta = "" if eta in ("N/A", "NA", "Unknown") else eta
            if status == "finished":
                self.parts_done += 1
                self.bytes_done += total or done
                if self.parts_done >= self.parts:
                    self.status, self.percent = "converting", 100.0
                    return
                pct, done, total = 0.0, 0, 0  # la parte finita è già in bytes_done
            elif not self.cancelled:
                self.status = "downloading"
            if self.parts == 1:
                if pct is not None:
                    self.percent = pct
            elif self.size_estimate:
                # avanzamento complessivo in byte: la parte video pesa quasi tutto
                current = self.bytes_done + done
                self.percent = min(99.0, 100.0 * current / max(self.size_estimate, self.bytes_done + total))
            elif pct is not None:
                self.percent = 100.0 * (self.parts_done + pct / 100) / self.parts
        elif line.startswith("TRIP_INFO "):
            fid, size, width, height, fps, hdr = (line[len("TRIP_INFO "):].split("|") + [""] * 6)[:6]
            self.parts = max(1, len(fid.strip().split("+")))
            self.size_estimate = to_number(size) or 0
            if FORMATS[self.fmt].get("video"):
                self.quality = quality_label(to_number(width), to_number(height), to_number(fps), hdr.strip())
        elif line.startswith("TRIP_TITLE "):
            self.title = line[len("TRIP_TITLE "):].strip()
        elif line.startswith("TRIP_FILE "):
            self.filepath = line[len("TRIP_FILE "):].strip()
        elif line.startswith("ERROR:"):
            self.detail = line[len("ERROR:"):].strip()

    def _finish(self, code):
        if self.cancelled:
            self.status = "cancelled"
            return
        path = self.filepath if self.filepath and os.path.isfile(self.filepath) else self._find_output()
        if code == 0 and path:
            self.filepath = path
            self.size = os.path.getsize(path)
            self.percent = 100.0
            self.status = "done"
            log.info("job %s: completato %s", self.id, path)
            return
        if not self.detail:
            tail = [l for l in self.lines if l.strip() and not l.startswith("TRIP_")]
            self.detail = tail[-1] if tail else "yt-dlp è terminato con codice %s" % code
        self.error = friendly_error(self.detail)
        self.status = "error"
        log.warning("job %s: errore %s", self.id, self.detail)

    def _find_output(self):
        # ripiego se il percorso stampato da yt-dlp non è leggibile
        try:
            candidates = [p for ext in FORMATS[self.fmt]["exts"] for p in self.outdir.glob("*." + ext)
                          if p.stat().st_mtime >= self.created - 2]
        except OSError:
            return None
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: p.stat().st_mtime))

    def cancel(self):
        self.cancelled = True
        if not self.proc or self.proc.poll() is not None:
            return
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True, **NO_WINDOW)
        else:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass


# ---------------------------------------------------------------------------
# Stato dell'applicazione


class TripYTD:
    def __init__(self, outdir_override=None):
        self.lock = threading.RLock()
        self.config = self._load_config()
        self.outdir_override = Path(outdir_override).expanduser() if outdir_override else None
        self.jobs = []
        self.last_seen = time.time()
        self.bye_at = 0.0
        self.setup_running = False
        self.setup_error = None
        self.setup_progress = {c["id"]: 0.0 for c in COMPONENTS}
        self.engine_version = None
        self.engine_updating = False
        self.engine_message = None

    # configurazione

    def _load_config(self):
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_config(self):
        try:
            CONFIG_FILE.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except OSError as e:
            log.warning("config non salvata: %s", e)

    @property
    def outdir(self):
        return self.outdir_override or Path(self.config.get("outdir") or DEFAULT_OUT)

    # presenza della pagina

    def touch(self):
        self.last_seen = time.time()

    def bye(self):
        self.bye_at = time.time()

    def busy(self):
        return self.setup_running or self.engine_updating or any(j.active for j in self.jobs)

    def watchdog(self, server):
        while True:
            time.sleep(5)
            if self.busy():
                continue
            now = time.time()
            closed = self.bye_at and self.last_seen < self.bye_at and now - self.bye_at > BYE_GRACE
            if closed or now - self.last_seen > IDLE_TIMEOUT:
                log.info("pagina chiusa, arresto del server")
                server.shutdown()
                return

    def quit(self, server):
        """Annulla i download in corso e chiude il server (usato dagli installer)."""
        log.info("richiesta di chiusura")
        for job in list(self.jobs):
            if job.active:
                job.cancel()
        threading.Thread(target=server.shutdown, daemon=True).start()

    # componenti

    def installed(self):
        return all(component_installed(c) for c in COMPONENTS)

    def start_setup(self):
        with self.lock:
            if self.setup_running:
                return
            self.setup_running = True
            self.setup_error = None
        threading.Thread(target=self._setup, daemon=True).start()

    def _setup(self):
        try:
            BIN.mkdir(parents=True, exist_ok=True)
            WORK.mkdir(parents=True, exist_ok=True)
            blocker = setup_blocker()
            if blocker:
                raise RuntimeError(blocker)
            for c in COMPONENTS:
                cid = c["id"]
                if component_installed(c):
                    self.setup_progress[cid] = 1.0
                    continue
                log.info("installo %s", cid)

                def progress(f, cid=cid):
                    self.setup_progress[cid] = f

                c["install"](BIN, progress)
                self._check(c)
                self.setup_progress[cid] = 1.0
            self.engine_version = ytdlp_version()
            self.config["last_update_check"] = time.time()
            self._save_config()
        except Exception as e:  # mostra qualsiasi errore nella pagina
            log.exception("installazione non riuscita")
            self.setup_error = str(e) or e.__class__.__name__
        finally:
            self.setup_running = False

    def _check(self, c):
        for name in c["files"]:
            path = BIN / name
            args = ["-hide_banner", "-version"] if name.startswith("ff") else ["--version"]
            try:
                r = subprocess.run([str(path)] + args, capture_output=True, timeout=120, env=tool_env(), **NO_WINDOW)
                ok = r.returncode == 0
                detail = r.stderr.decode(errors="replace").strip()
            except (OSError, subprocess.SubprocessError) as e:
                ok, detail = False, str(e)
            if not ok:
                for f in c["files"]:
                    if (BIN / f).exists():
                        (BIN / f).unlink()
                raise RuntimeError("%s non si avvia: %s" % (name, detail or "errore sconosciuto"))

    # motore yt-dlp

    def warm_up(self):
        self.engine_version = ytdlp_version()
        if time.time() - self.config.get("last_update_check", 0) > UPDATE_EVERY:
            self.update_engine()

    def update_engine(self):
        if not self.installed():
            return
        with self.lock:
            if self.engine_updating:
                return
            self.engine_updating = True
            self.engine_message = None
        threading.Thread(target=self._update_engine, daemon=True).start()

    def _update_engine(self):
        try:
            r = subprocess.run([str(YTDLP), "-U"], capture_output=True, text=True, timeout=300,
                               env=tool_env(), **NO_WINDOW)
            out = (r.stdout + "\n" + r.stderr).strip()
            m = re.search(r"Updated yt-dlp to \S*?@?([\d.]+)", out)
            if m:
                self.engine_message = "Motore aggiornato alla versione %s." % m.group(1)
            elif "up to date" in out:
                self.engine_message = "Il motore è già aggiornato."
            else:
                self.engine_message = "Aggiornamento non riuscito: " + (out.splitlines()[-1] if out else "errore sconosciuto")
            self.config["last_update_check"] = time.time()
            self._save_config()
        except (OSError, subprocess.SubprocessError) as e:
            self.engine_message = "Aggiornamento non riuscito: %s" % e
        finally:
            self.engine_version = ytdlp_version()
            self.engine_updating = False

    # download

    def add_job(self, url, fmt):
        if fmt not in FORMATS:
            raise ValueError("Formato non valido.")
        vid = video_id(url)
        if not vid:
            if is_youtube_host(url):
                raise ValueError("Incolla il link di un singolo video, non di una playlist o di un canale.")
            raise ValueError("Non sembra un link YouTube. Esempio: https://www.youtube.com/watch?v=…")
        if not self.installed():
            raise ValueError("Installa prima i componenti.")
        outdir = self.outdir
        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            where = ("nelle impostazioni di sicurezza di Windows" if IS_WIN else
                     "in Impostazioni di Sistema › Privacy e sicurezza › File e cartelle" if IS_MAC else
                     "modificando i permessi della cartella")
            raise ValueError("Trip YTD non può scrivere in %s. Scegli un'altra cartella o consenti l'accesso %s."
                             % (human_path(outdir), where))
        job = Job(url.strip(), vid, fmt, outdir)
        with self.lock:
            self.jobs.insert(0, job)
            del self.jobs[30:]
        threading.Thread(target=job.run, daemon=True).start()
        return job

    def job(self, jid):
        return next((j for j in self.jobs if j.id == jid), None)

    def dismiss(self, jid):
        with self.lock:
            self.jobs = [j for j in self.jobs if j.id != jid or j.active]

    def choose_outdir(self):
        start = self.outdir if self.outdir.is_dir() else Path.home()
        chosen = choose_folder_dialog(start)
        if not chosen:
            return False
        self.outdir_override = None
        self.config["outdir"] = chosen
        self._save_config()
        return True

    def state(self):
        return {
            "app": {"name": APP_NAME, "version": VERSION},
            "platform": "windows" if IS_WIN else "mac" if IS_MAC else "linux",
            "setup": {
                "installed": self.installed(),
                "running": self.setup_running,
                "error": self.setup_error,
                "components": [
                    {"id": c["id"], "label": c["label"], "desc": c["desc"], "installed": component_installed(c),
                     "progress": round(self.setup_progress[c["id"]], 3)}
                    for c in COMPONENTS
                ],
                "location": human_path(SUPPORT),
                "size": SETUP_SIZE,
            },
            "engine": {"version": self.engine_version, "updating": self.engine_updating,
                       "message": self.engine_message},
            "outdir": human_path(self.outdir),
            "jobs": [j.to_dict() for j in self.jobs],
        }


# ---------------------------------------------------------------------------
# Server HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "TripYTD/" + VERSION

    def log_message(self, fmt, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def _host_ok(self):
        # blocca il DNS rebinding: la pagina deve arrivare da 127.0.0.1 o localhost
        host = (self.headers.get("Host") or "").lower()
        return host in ("%s:%d" % (HOST, PORT), "localhost:%d" % PORT)

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        if path == "/api/ping":
            return self._send(200, {"app": APP_NAME, "version": VERSION})
        self.app.touch()
        if path in ("/", "/index.html"):
            return self._send(200, (HERE / "ui.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/icon.svg" and (HERE / "icon.svg").exists():
            return self._send(200, (HERE / "icon.svg").read_bytes(), "image/svg+xml")
        if path == "/api/state":
            return self._send(200, self.app.state())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if self.path == "/api/bye":
            self.app.bye()
            return self._send(200, {})
        # un'intestazione personalizzata impedisce ad altri siti di inviare richieste (CORS)
        if self.headers.get("X-Trip-YTD") != "1":
            return self._send(403, {"error": "forbidden"})
        self.app.touch()
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except ValueError:
            return self._send(400, {"error": "Richiesta non valida."})

        app = self.app
        if self.path == "/api/quit":
            self._send(200, {"ok": True})
            return app.quit(self.server)
        if self.path == "/api/setup":
            app.start_setup()
            return self._send(200, {"ok": True})
        if self.path == "/api/jobs":
            try:
                job = app.add_job(str(body.get("url", "")), str(body.get("format", "mp3")))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            return self._send(200, job.to_dict())
        if self.path == "/api/update":
            app.update_engine()
            return self._send(200, {"ok": True})
        if self.path == "/api/outdir/choose":
            try:
                ok = app.choose_outdir()
            except RuntimeError as e:
                return self._send(400, {"error": str(e)})
            return self._send(200, {"ok": ok, "outdir": human_path(app.outdir)})
        if self.path == "/api/outdir/open":
            app.outdir.mkdir(parents=True, exist_ok=True)
            open_folder(app.outdir)
            return self._send(200, {"ok": True})

        m = re.fullmatch(r"/api/jobs/([0-9a-f]+)/(cancel|dismiss|reveal|play)", self.path)
        job = app.job(m.group(1)) if m else None
        if not job:
            return self._send(404, {"error": "Download non trovato."})
        action = m.group(2)
        if action == "cancel":
            job.cancel()
        elif action == "dismiss":
            app.dismiss(job.id)
        elif job.status == "done" and job.filepath and os.path.isfile(job.filepath):
            if action == "reveal":
                reveal_file(job.filepath)
            else:
                play_file(job.filepath, video=FORMATS[job.fmt].get("video", False))
        else:
            return self._send(404, {"error": "Il file non esiste più."})
        return self._send(200, {"ok": True})


def already_running():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL + "api/ping", timeout=1.5) as r:
            return json.load(r).get("app") == APP_NAME
    except Exception:
        return False


def stop_running():
    """Chiede a un Trip YTD già aperto di chiudersi e attende fino a 5 secondi."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(URL + "api/quit", data=b"{}", method="POST",
                                 headers={"X-Trip-YTD": "1", "Content-Type": "application/json"})
    try:
        opener.open(req, timeout=3).close()
    except Exception:
        return  # non era aperto
    for _ in range(50):
        if not already_running():
            return
        time.sleep(0.1)


def main():
    ap = argparse.ArgumentParser(description="Trip YTD: audio (MP3 320k, WAV) e video da YouTube.")
    ap.add_argument("--no-browser", action="store_true", help="non aprire il browser all'avvio")
    ap.add_argument("--out", help="cartella di destinazione per questa sessione")
    ap.add_argument("--shortcuts", action="store_true", help="Linux: aggiunge Trip YTD al menu delle applicazioni")
    ap.add_argument("--quit", action="store_true", help="chiude Trip YTD se è aperto")
    args = ap.parse_args()
    if args.quit:
        return stop_running()

    SUPPORT.mkdir(parents=True, exist_ok=True)
    if args.shortcuts and IS_LINUX:
        create_linux_shortcut()

    if already_running():
        if not args.no_browser:
            open_browser()
        return

    # FileHandler invece di basicConfig(encoding=…), che richiede Python 3.9
    logging.basicConfig(handlers=[logging.FileHandler(str(LOG_FILE), mode="w", encoding="utf-8")],
                        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    shutil.rmtree(WORK, ignore_errors=True)  # residui di download interrotti

    app = TripYTD(args.out)
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        log.error("porta %d occupata: %s", PORT, e)
        return
    server.daemon_threads = True
    server.app = app
    log.info("Trip YTD %s (%s) in ascolto su %s", VERSION, sys.platform, URL)

    threading.Thread(target=app.watchdog, args=(server,), daemon=True).start()
    if app.installed():
        threading.Thread(target=app.warm_up, daemon=True).start()
    if not args.no_browser:
        open_browser()
    server.serve_forever()


if __name__ == "__main__":
    main()
