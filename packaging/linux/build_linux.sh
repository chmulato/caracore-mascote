#!/usr/bin/env bash
# Build Linux do Gaspar: PyInstaller + .deb + AppImage.
#
# Uso:
#   bash packaging/linux/build_linux.sh
#   bash packaging/linux/build_linux.sh --deb-only
#   bash packaging/linux/build_linux.sh --appimage-only
#   bash packaging/linux/build_linux.sh --skip-pyinstaller
#
# Requisitos: python3, tkinter, PyInstaller (requirements-dev.txt).
# .deb: dpkg-deb (pacote dpkg-dev). AppImage: appimagetool.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="${ROOT}/dist/linux"
WORK="${ROOT}/build/linux"
VERSION="$(cd "$ROOT" && python3 -c 'import gaspar; print(gaspar.__version__)')"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
DESKTOP_FILE="${ROOT}/packaging/linux/gaspar.desktop"
BLACKBOX_DESKTOP_FILE="${ROOT}/packaging/linux/gaspar-blackbox.desktop"
APPIMAGE_NAME="Gaspar-${VERSION}-${ARCH}.AppImage"

usage() {
  sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

die() {
  echo "ERRO: $*" >&2
  exit 1
}

resize_icon() {
  python3 - "$1" "$2" "$3" <<'PY'
import sys
from PIL import Image

source, destination, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
with Image.open(source) as image:
    icon = image.convert("RGBA")
    icon.thumbnail((size, size), Image.LANCZOS)
    icon.save(destination)
PY
}

prepare_pyinstaller() {
  rm -rf "$DIST/gaspar" "$DIST/gaspar_blackbox" "$WORK/pyinstaller"
  mkdir -p "$DIST" "$WORK/pyinstaller"
  echo ">> PyInstaller (Gaspar)"
  (cd "$ROOT" && python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath "$DIST" \
    --workpath "$WORK/pyinstaller" \
    "$ROOT/packaging/linux/gaspar.spec")
  echo ">> PyInstaller (BlackBox)"
  (cd "$ROOT" && python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath "$DIST" \
    --workpath "$WORK/pyinstaller" \
    "$ROOT/packaging/linux/gaspar_blackbox.spec")
  [ -x "$DIST/gaspar/gaspar" ] || die "binario nao gerado em $DIST/gaspar/gaspar"
  [ -x "$DIST/gaspar_blackbox/gaspar_blackbox" ] || die "binario nao gerado em $DIST/gaspar_blackbox/gaspar_blackbox"
}

build_deb() {
  command -v dpkg-deb >/dev/null 2>&1 || die "dpkg-deb nao encontrado (instale dpkg-dev)."
  local stage="$WORK/deb/gaspar_${VERSION}_${ARCH}"
  rm -rf "$stage"
  mkdir -p \
    "$stage/DEBIAN" \
    "$stage/opt/caracore/gaspar" \
    "$stage/opt/caracore/gaspar_blackbox" \
    "$stage/usr/bin" \
    "$stage/usr/share/applications" \
    "$stage/usr/share/icons/hicolor/256x256/apps" \
    "$stage/usr/share/pixmaps"

  cp -a "$DIST/gaspar/." "$stage/opt/caracore/gaspar/"
  cp -a "$DIST/gaspar_blackbox/." "$stage/opt/caracore/gaspar_blackbox/"
  cat > "$stage/usr/bin/gaspar" <<'WRAPPER'
#!/bin/sh
exec /opt/caracore/gaspar/gaspar "$@"
WRAPPER
  cat > "$stage/usr/bin/gaspar-blackbox" <<'WRAPPER'
#!/bin/sh
exec /opt/caracore/gaspar_blackbox/gaspar_blackbox "$@"
WRAPPER
  chmod 755 "$stage/usr/bin/gaspar" "$stage/usr/bin/gaspar-blackbox"

  install -m 644 "$DESKTOP_FILE" "$stage/usr/share/applications/gaspar.desktop"
  install -m 644 "$BLACKBOX_DESKTOP_FILE" "$stage/usr/share/applications/gaspar-blackbox.desktop"
  resize_icon "$ROOT/assets/gaspar.png" "$stage/usr/share/icons/hicolor/256x256/apps/gaspar.png" 256
  cp "$stage/usr/share/icons/hicolor/256x256/apps/gaspar.png" "$stage/usr/share/pixmaps/gaspar.png"

  local installed_kb
  installed_kb="$(du -sk "$stage/opt" | cut -f1)"
  cat > "$stage/DEBIAN/control" <<CONTROL
Package: gaspar
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: libx11-6, libxext6, libxtst6, libxss1
Recommends: policykit-1
Installed-Size: ${installed_kb}
Maintainer: Cara Core Informatica
Description: Gaspar - Mascote Cara Core
 Mascote flutuante com simulacao discreta de presenca. Mantem
 Teams/Slack ativos, registra ciclos em log e inclui o BlackBox
 para bloqueio de telemetria via arquivo hosts.
CONTROL

  cat > "$stage/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
fi
exit 0
POSTINST
  chmod 755 "$stage/DEBIAN/postinst"

  local output="$DIST/gaspar_${VERSION}_${ARCH}.deb"
  echo ">> dpkg-deb"
  if dpkg-deb --help 2>&1 | grep -q -- '--root-owner-group'; then
    dpkg-deb --root-owner-group --build "$stage" "$output"
  else
    dpkg-deb --build "$stage" "$output"
  fi
  echo "Pacote: $output"
}

build_appimage() {
  local tool="${APPIMAGETOOL:-}"
  if [ -z "$tool" ]; then
    tool="$(command -v appimagetool || true)"
  fi
  if [ -z "$tool" ] || [ ! -x "$tool" ]; then
    die "appimagetool nao encontrado. Baixe em https://github.com/AppImage/appimagetool/releases e defina APPIMAGETOOL=/caminho/appimagetool."
  fi

  local appdir="$WORK/appimage/Gaspar.AppDir"
  rm -rf "$appdir"
  mkdir -p \
    "$appdir/usr/bin/gaspar" \
    "$appdir/usr/bin/gaspar_blackbox" \
    "$appdir/usr/share/applications" \
    "$appdir/usr/share/icons/hicolor/256x256/apps"

  cp -a "$DIST/gaspar/." "$appdir/usr/bin/gaspar/"
  cp -a "$DIST/gaspar_blackbox/." "$appdir/usr/bin/gaspar_blackbox/"
  install -m 644 "$DESKTOP_FILE" "$appdir/gaspar.desktop"
  install -m 644 "$DESKTOP_FILE" "$appdir/usr/share/applications/gaspar.desktop"
  install -m 644 "$BLACKBOX_DESKTOP_FILE" "$appdir/usr/share/applications/gaspar-blackbox.desktop"
  resize_icon "$ROOT/assets/gaspar.png" "$appdir/gaspar.png" 256
  install -m 644 "$appdir/gaspar.png" "$appdir/usr/share/icons/hicolor/256x256/apps/gaspar.png"

  cat > "$appdir/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/gaspar/gaspar" "$@"
APPRUN
  chmod 755 "$appdir/AppRun"

  echo ">> appimagetool"
  APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$tool" "$appdir" "$DIST/$APPIMAGE_NAME"
  echo "AppImage: $DIST/$APPIMAGE_NAME"
}

BUILD_DEB=1
BUILD_APPIMAGE=1
SKIP_BUILD=0

while [ $# -gt 0 ]; do
  case "$1" in
    --deb-only) BUILD_APPIMAGE=0 ;;
    --appimage-only) BUILD_DEB=0 ;;
    --skip-pyinstaller) SKIP_BUILD=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opcao desconhecida: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

[ "$BUILD_DEB" = 1 ] || [ "$BUILD_APPIMAGE" = 1 ] || die "nada a gerar; remova --deb-only/--appimage-only."

command -v python3 >/dev/null 2>&1 || die "python3 nao encontrado."
python3 -c 'import tkinter' 2>/dev/null || die "tkinter ausente (instale python3-tk)."

for asset in gaspar.png gaspar.ico gaspar_flutuando.gif; do
  [ -f "$ROOT/assets/$asset" ] || die "ativo ausente: assets/$asset"
done

if [ "$SKIP_BUILD" = 0 ]; then
  python3 -c 'import PyInstaller' 2>/dev/null || die "PyInstaller ausente. Rode: python3 -m pip install -r requirements-dev.txt"
  python3 -c 'import pyautogui' 2>/dev/null || echo "AVISO: pyautogui ausente; o app empacotado pode falhar ao simular mouse/teclado." >&2
  prepare_pyinstaller
else
  [ -x "$DIST/gaspar/gaspar" ] || die "build anterior ausente; rode sem --skip-pyinstaller."
fi

if [ "$BUILD_DEB" = 1 ]; then
  build_deb
fi
if [ "$BUILD_APPIMAGE" = 1 ]; then
  build_appimage
fi

echo
echo "Artefatos em $DIST:"
ls -lh "$DIST" | grep -E '\.(deb|AppImage)$' || true
echo "Observacao: o overlay usa X11/XWayland (shape + click-through). Em Wayland puro, use XWayland."
