#!/usr/bin/env bash
# Adapted from ELI_Legal: packaging/macos/build.sh @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
# Build the macOS disk image: PyInstaller makes "ELI Creation Station.app", hdiutil wraps it in a .dmg.
#
#   packaging/macos/build.sh
#
# Run on the oldest macOS you intend to support, once per architecture (Apple silicon, Intel).
# An unsigned application is blocked by Gatekeeper. To sign and notarise, set:
#   ELI_CREATION_CODESIGN_IDENTITY   "Developer ID Application: Your Name (TEAMID)"
#   ELI_CREATION_NOTARY_PROFILE      a keychain profile created with `xcrun notarytool store-credentials`
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [ -n "${PYTHON:-}" ]; then PY="$PYTHON"; elif [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
"$PY" -m pip install --quiet -e ".[all,build]"
VERSION="$("$PY" -c 'import eli_creation; print(eli_creation.__version__)')"
ARCH="$(uname -m)"
OUT="dist/installers"
DMG="$OUT/ELI_Creation_Station-$VERSION-macos-$ARCH.dmg"

"$PY" scripts/third_party_notices.py
"$PY" -m PyInstaller packaging/pyinstaller/eli_creation.spec --noconfirm --distpath build/dist --workpath build/work --log-level WARN
APP="build/dist/ELI Creation Station.app"
[ -d "$APP" ] || { echo "PyInstaller did not produce $APP" >&2; exit 1; }
"$APP/Contents/MacOS/eli-creation" --help >/dev/null

if [ -n "${ELI_CREATION_CODESIGN_IDENTITY:-}" ]; then
  codesign --force --deep --options runtime --timestamp --sign "$ELI_CREATION_CODESIGN_IDENTITY" "$APP"
  codesign --verify --deep --strict "$APP"
else
  echo "NOTE: not signed. Gatekeeper will refuse to open it until the user allows it explicitly." >&2
fi

mkdir -p "$OUT" build/dmg
rm -rf build/dmg/* "$DMG"
cp -R "$APP" build/dmg/
cp LICENSE packaging/INSTALL_NOTICE.txt THIRD_PARTY_NOTICES.md build/dmg/
ln -s /Applications build/dmg/Applications
# hdiutil fails now and then with "Resource busy" while the system still holds the new volume
# (indexing, a mount just released); it succeeds when tried again a little later.
for attempt in 1 2 3 4 5; do
  if hdiutil create -volname "ELI Creation Station $VERSION" -srcfolder build/dmg -ov -format UDZO "$DMG" >/dev/null; then
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "hdiutil could not create the disk image after $attempt attempts" >&2
    exit 1
  fi
  echo "hdiutil create failed (attempt $attempt); trying again in $((attempt * 10)) s" >&2
  sleep $((attempt * 10))
done

if [ -n "${ELI_CREATION_CODESIGN_IDENTITY:-}" ] && [ -n "${ELI_CREATION_NOTARY_PROFILE:-}" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$ELI_CREATION_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi
(cd "$OUT" && shasum -a 256 "$(basename "$DMG")" > "SHA256SUMS-macos-$ARCH")
echo "Built $DMG"
