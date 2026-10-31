#!/bin/bash
# Crea i pacchetti di Trip YTD in dist/:
#   Trip YTD.app               app per macOS, pronta all'uso
#   Trip YTD - macOS.zip       la stessa app, da condividere
#   Trip YTD - Windows.zip     cartella per Windows con Python incluso
set -euo pipefail
cd "$(dirname "$0")"

# Python "embeddable" per Windows 64 bit (python.org), con il suo SHA-256 ufficiale
PY_VERSION=3.14.10
PY_SHA256=90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159
PY_ZIP="python-$PY_VERSION-embed-amd64.zip"

DIST=dist
BUILD=build
mkdir -p "$DIST" "$BUILD/cache"

# --- icone (generate una volta sola) -----------------------------------------
if [ ! -f src/icon.icns ] || [ ! -f src/icon.ico ]; then
  tmp="$(mktemp -d)"
  swift src/make_icon.swift "$tmp/icon_1024.png"
  mkdir "$tmp/icon.iconset"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$tmp/icon_1024.png" --out "$tmp/icon.iconset/icon_${s}x${s}.png" >/dev/null
    sips -z $((s * 2)) $((s * 2)) "$tmp/icon_1024.png" --out "$tmp/icon.iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$tmp/icon.iconset" -o src/icon.icns
  for s in 16 24 32 48 64 256; do
    sips -z $s $s "$tmp/icon_1024.png" --out "$tmp/ico_$s.png" >/dev/null
  done
  # .ico con immagini PNG incorporate (supportato da Windows Vista in poi)
  /usr/bin/python3 -I - "$tmp" src/icon.ico <<'EOF'
import struct, sys
src, out = sys.argv[1], sys.argv[2]
sizes = [16, 24, 32, 48, 64, 256]
images = [open("%s/ico_%d.png" % (src, s), "rb").read() for s in sizes]
offset = 6 + 16 * len(sizes)
header = struct.pack("<HHH", 0, 1, len(sizes))
entries = b""
for s, data in zip(sizes, images):
    entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
open(out, "wb").write(header + entries + b"".join(images))
EOF
  rm -rf "$tmp"
fi

# --- macOS ---------------------------------------------------------------------
APP="$DIST/Trip YTD.app"
RES="$APP/Contents/Resources"
rm -rf "$APP"
osacompile -o "$APP" src/launcher.applescript
cp src/trip_ytd.py src/ui.html src/icon.svg "$RES/"
cp src/icon.icns "$RES/applet.icns"
rm -f "$RES/Assets.car"

plist="$APP/Contents/Info.plist"
pb() { /usr/libexec/PlistBuddy -c "$1" "$plist"; }
pb "Set :CFBundleName Trip YTD"
pb "Set :CFBundleIdentifier com.trip.ytd" 2>/dev/null || pb "Add :CFBundleIdentifier string com.trip.ytd"
pb "Add :CFBundleShortVersionString string 1.1" 2>/dev/null || pb "Set :CFBundleShortVersionString 1.1"
pb "Delete :CFBundleIconName" 2>/dev/null || true

# la firma ad-hoc è necessaria su Apple Silicon dopo aver modificato il pacchetto
codesign --force --deep --sign - "$APP" 2>/dev/null
rm -f "$DIST/Trip YTD - macOS.zip"
ditto -c -k --keepParent "$APP" "$DIST/Trip YTD - macOS.zip"
echo "Creato: $APP"
echo "Creato: $DIST/Trip YTD - macOS.zip"

# --- Windows -------------------------------------------------------------------
if [ ! -f "$BUILD/cache/$PY_ZIP" ]; then
  curl -fsSL --retry 2 -o "$BUILD/cache/$PY_ZIP.part" "https://www.python.org/ftp/python/$PY_VERSION/$PY_ZIP"
  mv "$BUILD/cache/$PY_ZIP.part" "$BUILD/cache/$PY_ZIP"
fi
echo "$PY_SHA256  $BUILD/cache/$PY_ZIP" | shasum -a 256 -c --status || {
  echo "Checksum di $PY_ZIP non valido" >&2; rm -f "$BUILD/cache/$PY_ZIP"; exit 1; }

WIN="$BUILD/windows/Trip YTD"
rm -rf "$BUILD/windows"
mkdir -p "$WIN/app" "$WIN/runtime"
unzip -q "$BUILD/cache/$PY_ZIP" -d "$WIN/runtime"
cp src/trip_ytd.py src/ui.html src/icon.svg src/icon.ico "$WIN/app/"

# i file .cmd e .txt per Windows vogliono le terminazioni di riga CRLF
crlf() { sed 's/$/\r/' "$1" > "$2"; }
crlf src/windows/avvia.cmd "$WIN/Avvia Trip YTD.cmd"
{ printf '\xef\xbb\xbf'; sed 's/$/\r/' src/windows/LEGGIMI.txt; } > "$WIN/LEGGIMI.txt"  # BOM: Blocco note la legge come UTF-8

rm -f "$DIST/Trip YTD - Windows.zip"
(cd "$BUILD/windows" && zip -qrX "../../$DIST/Trip YTD - Windows.zip" "Trip YTD")
echo "Creato: $DIST/Trip YTD - Windows.zip"
