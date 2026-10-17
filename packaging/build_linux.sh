#!/usr/bin/env bash
# Build the Linux one-dir bundle, tar.gz and AppImage. Run anywhere; works from repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${PYTHON:-}" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; else PYTHON=python3; fi
fi
VER="$($PYTHON -c 'import pcc; print(pcc.__version__)')"
OUT=packaging/out
TOOLS="$OUT/tools"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
mkdir -p "$OUT" "$TOOLS"

echo "==> PyInstaller (version $VER)"
$PYTHON -m PyInstaller --noconfirm --clean packaging/pcc.spec

echo "==> tarball"
TARBALL="$OUT/PrintCostCalculator-$VER-linux-x86_64.tar.gz"
tar -C dist -czf "$TARBALL" PrintCostCalculator

echo "==> AppDir"
APPDIR="$OUT/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a dist/PrintCostCalculator/. "$APPDIR/usr/bin/"
cp packaging/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp packaging/pcc.desktop "$APPDIR/print-cost-calculator.desktop"
cp pcc/assets/icon.png "$APPDIR/print-cost-calculator.png"
cp pcc/assets/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/print-cost-calculator.png"

echo "==> AppImage"
TOOL="$TOOLS/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
  if command -v curl >/dev/null 2>&1; then curl -fL -o "$TOOL" "$APPIMAGETOOL_URL"
  else wget -O "$TOOL" "$APPIMAGETOOL_URL"; fi
  chmod +x "$TOOL"
fi
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT/PrintCostCalculator-$VER-x86_64.AppImage"

echo "==> done"
ls -lh "$OUT"/PrintCostCalculator-"$VER"-*
