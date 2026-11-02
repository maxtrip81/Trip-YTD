#!/bin/bash
# Crea i pacchetti di Trip YTD in dist/ (su un Mac):
#   Trip YTD.app            app per macOS con Python incluso (Apple Silicon e Intel)
#   Trip-YTD-macOS.pkg      installer per macOS
#   Trip-YTD-Linux.tar.gz   cartella per Linux (usa il Python del sistema)
# L'installer per Windows si crea su Windows con src/windows/build.ps1.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' src/trip_ytd.py)

# Python per macOS (python-build-standalone di Astral), uno per architettura, con il suo SHA-256
PBS_RELEASE=20261026
PBS_PYTHON=3.14.10
PBS_SHA256_aarch64=95eb8c87d16af37c54e9765e31d8c56c0d8ffa9968ea0f704f73a9b83f84e9f9
PBS_SHA256_x86_64=2fd8becd48cf0ff5f0a15df3c0db7cae7aa708dcaacf901bd30d6cdd6229370b

DIST=dist
BUILD=build
mkdir -p "$DIST" "$BUILD/cache"

# --- icone (generate una volta sola) -----------------------------------------
if [ ! -f src/icon.icns ] || [ ! -f src/icon.ico ] || [ ! -f src/icon.png ]; then
  tmp="$(mktemp -d)"
  swift src/make_icon.swift "$tmp/icon_1024.png"
  mkdir "$tmp/icon.iconset"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$tmp/icon_1024.png" --out "$tmp/icon.iconset/icon_${s}x${s}.png" >/dev/null
    sips -z $((s * 2)) $((s * 2)) "$tmp/icon_1024.png" --out "$tmp/icon.iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$tmp/icon.iconset" -o src/icon.icns
  sips -z 256 256 "$tmp/icon_1024.png" --out src/icon.png >/dev/null  # menu delle applicazioni di Linux
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

# --- macOS: app ----------------------------------------------------------------
mac_python() {  # $1 = aarch64 | x86_64, $2 = cartella di destinazione
  local name="cpython-$PBS_PYTHON+$PBS_RELEASE-$1-apple-darwin-install_only_stripped.tar.gz"
  local sha_var="PBS_SHA256_$1"
  local file="$BUILD/cache/$name"
  if [ ! -f "$file" ]; then
    curl -fsSL --retry 2 -o "$file.part" \
      "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_RELEASE/${name//+/%2B}"
    mv "$file.part" "$file"
  fi
  echo "${!sha_var}  $file" | shasum -a 256 -c --status || {
    echo "Checksum di $name non valido" >&2; rm -f "$file"; exit 1; }
  mkdir -p "$2"
  tar -xzf "$file" -C "$2" --strip-components 1
  # tiene solo ciò che serve a Trip YTD: via Tcl/Tk, pip, header e documentazione
  (cd "$2" && rm -rf include share bin/idle* bin/pip* bin/pydoc* bin/python*-config \
    lib/pkgconfig lib/itcl* lib/thread* lib/tcl* lib/tk* lib/libtcl* \
    lib/python3.*/{idlelib,tkinter,turtledemo,ensurepip,pydoc_data,config-*} \
    lib/python3.*/site-packages/* lib/python3.*/lib-dynload/_tkinter*)
}

APP="$DIST/Trip YTD.app"
RES="$APP/Contents/Resources"
rm -rf "$APP"
osacompile -o "$APP" src/launcher.applescript
cp src/trip_ytd.py src/ui.html src/icon.svg src/mac/launch.sh "$RES/"
cp src/icon.icns "$RES/applet.icns"
rm -f "$RES/Assets.car"
mac_python aarch64 "$RES/python-arm64"
mac_python x86_64 "$RES/python-x86_64"

# precompila la libreria standard, così l'app non scrive nulla al proprio interno
for arch in arm64 x86_64; do
  if "$RES/python-$arch/bin/python3" -c '' 2>/dev/null; then
    "$RES/python-$arch/bin/python3" -m compileall -q -j 0 --invalidation-mode unchecked-hash \
      "$RES"/python-arm64/lib/python3.* "$RES"/python-x86_64/lib/python3.* >/dev/null
    break
  fi
done

plist="$APP/Contents/Info.plist"
pb() { /usr/libexec/PlistBuddy -c "$1" "$plist"; }
pb "Set :CFBundleName Trip YTD"
pb "Set :CFBundleIdentifier com.trip.ytd" 2>/dev/null || pb "Add :CFBundleIdentifier string com.trip.ytd"
pb "Add :CFBundleShortVersionString string $VERSION" 2>/dev/null || pb "Set :CFBundleShortVersionString $VERSION"
pb "Add :LSMinimumSystemVersion string 11.0" 2>/dev/null || pb "Set :LSMinimumSystemVersion 11.0"
pb "Delete :CFBundleIconName" 2>/dev/null || true

# la firma ad-hoc è necessaria su Apple Silicon dopo aver modificato il pacchetto
codesign --force --deep --sign - "$APP" 2>/dev/null
echo "Creato: $APP"

# --- macOS: installer .pkg -----------------------------------------------------
PKG="$BUILD/pkg"
rm -rf "$PKG"
mkdir -p "$PKG/root"
ditto "$APP" "$PKG/root/Trip YTD.app"
pkgbuild --analyze --root "$PKG/root" "$PKG/component.plist" >/dev/null
# installa sempre in Applicazioni, anche se sul Mac esiste un'altra copia dell'app
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" "$PKG/component.plist"
pkgbuild --quiet --root "$PKG/root" --component-plist "$PKG/component.plist" \
  --identifier com.trip.ytd --version "$VERSION" --install-location /Applications "$PKG/TripYTD.pkg"
sed "s/@VERSION@/$VERSION/g" src/mac/distribution.xml > "$PKG/distribution.xml"
productbuild --quiet --distribution "$PKG/distribution.xml" --resources src/mac/resources \
  --package-path "$PKG" "$DIST/Trip-YTD-macOS.pkg"
echo "Creato: $DIST/Trip-YTD-macOS.pkg"

# --- Linux ---------------------------------------------------------------------
LNX="$BUILD/linux/Trip YTD"
rm -rf "$BUILD/linux"
mkdir -p "$LNX/app"
cp src/trip_ytd.py src/ui.html src/icon.svg src/icon.png "$LNX/app/"
cp src/linux/trip-ytd src/linux/LEGGIMI.txt "$LNX/"
chmod 644 "$LNX/app/"* "$LNX/LEGGIMI.txt"
chmod 755 "$LNX/trip-ytd"
rm -f "$DIST/Trip-YTD-Linux.tar.gz"
# tar.gz conserva i permessi di esecuzione; niente attributi estesi né file ._ di macOS
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata --uid 0 --gid 0 --uname root --gname root \
  -czf "$DIST/Trip-YTD-Linux.tar.gz" -C "$BUILD/linux" "Trip YTD"
echo "Creato: $DIST/Trip-YTD-Linux.tar.gz"
