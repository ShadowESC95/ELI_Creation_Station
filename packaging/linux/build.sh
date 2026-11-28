#!/usr/bin/env bash
# Adapted from ELI_Legal: packaging/linux/build.sh @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
# Build the Linux installers: a self-extracting installer (.run), a Debian package (.deb), an
# AppImage and a plain archive (.tar.gz). Output goes to dist/installers with a SHA256SUMS file.
#
#   packaging/linux/build.sh            build everything
#   SKIP_FREEZE=1 packaging/linux/build.sh   reuse build/dist/eli-creation from an earlier run
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [ -n "${PYTHON:-}" ]; then PY="$PYTHON"; elif [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
VERSION="$("$PY" -c 'import eli_creation; print(eli_creation.__version__)')"
ARCH="$(uname -m)"
DEB_ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
STAGE="build/dist/eli-creation"
OUT="dist/installers"
NAME="ELI_Creation_Station-$VERSION-linux-$ARCH"

if [ -z "${SKIP_FREEZE:-}" ]; then
  "$PY" scripts/third_party_notices.py
  "$PY" -m PyInstaller packaging/pyinstaller/eli_creation.spec --noconfirm --distpath build/dist --workpath build/work --log-level WARN
fi
[ -x "$STAGE/eli-creation" ] || { echo "no frozen build at $STAGE" >&2; exit 1; }
# No GTK and no GLib I/O library in the bundle: they would load the user's system's plug-ins.
"$PY" packaging/linux/check_bundle.py --trim "$STAGE/_internal"
"$STAGE/eli-creation" --help >/dev/null
"$PY" packaging/linux/check_bundle.py "$STAGE/_internal"
cp packaging/INSTALL_NOTICE.txt "$STAGE/_internal/INSTALL_NOTICE.txt"
# The oldest C library the bundled files need: the installer says so if a machine is older.
GLIBC="$(find "$STAGE" -type f \( -name '*.so*' -o -name 'eli-creation*' \) -print0 | xargs -0 objdump -T 2>/dev/null \
  | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1 | cut -d_ -f2)"
mkdir -p "$OUT"
rm -f "$OUT/$NAME".* "$OUT"/eli-creation_"$VERSION"_*.deb

echo "==> archive"
tar -C build/dist --owner=0 --group=0 --numeric-owner -czf "$OUT/$NAME.tar.gz" eli-creation

echo "==> self-extracting installer"
SUM="$(sha256sum < "$OUT/$NAME.tar.gz" | cut -d' ' -f1)"
sed -e "s/@VERSION@/$VERSION/g" -e "s/@ARCH@/$ARCH/g" -e "s/@SHA256@/$SUM/g" -e "s/@GLIBC@/${GLIBC:-2.x}/g" \
  packaging/linux/installer_header.sh > "$OUT/$NAME.run"
cat "$OUT/$NAME.tar.gz" >> "$OUT/$NAME.run"
chmod 755 "$OUT/$NAME.run"

if command -v dpkg-deb >/dev/null 2>&1; then
  echo "==> Debian package"
  DEB="build/deb"
  rm -rf "$DEB"
  mkdir -p "$DEB/DEBIAN" "$DEB/opt/eli-creation" "$DEB/usr/bin" "$DEB/usr/share/applications" \
    "$DEB/usr/share/icons/hicolor/256x256/apps" "$DEB/usr/share/doc/eli-creation"
  cp -a "$STAGE" "$DEB/opt/eli-creation/app"
  for name in eli-creation eli-creation-gui; do
    printf '#!/bin/sh\n# ELI Creation Station launcher\nexec /opt/eli-creation/app/%s "$@"\n' "$name" > "$DEB/usr/bin/$name"
    chmod 755 "$DEB/usr/bin/$name"
  done
  cp src/eli_creation/gui/assets/eli_creation_256.png "$DEB/usr/share/icons/hicolor/256x256/apps/eli-creation.png"
  sed -e 's|^Exec=.*|Exec=/opt/eli-creation/app/eli-creation-gui|' -e 's|^Icon=.*|Icon=eli-creation|' -e '/^Path=/d' \
    packaging/eli-creation.desktop > "$DEB/usr/share/applications/eli-creation.desktop"
  cp THIRD_PARTY_NOTICES.md packaging/INSTALL_NOTICE.txt "$DEB/usr/share/doc/eli-creation/"
  { echo "ELI Creation Station $VERSION"; echo; [ -f LICENSE ] && cat LICENSE || echo "No licence file accompanies this build. All rights are reserved by the copyright holder unless a separate agreement says otherwise."; echo; echo "Third-party components: see THIRD_PARTY_NOTICES.md in this folder."; } > "$DEB/usr/share/doc/eli-creation/copyright"
  MAINTAINER="${ELI_CREATION_MAINTAINER:-$(git config user.name 2>/dev/null || echo 'ELI Creation Station') <$(git config user.email 2>/dev/null || echo 'unknown@invalid')>}"
  cat > "$DEB/DEBIAN/control" <<CONTROL
Package: eli-creation
Version: $VERSION
Section: graphics
Priority: optional
Architecture: $DEB_ARCH
Maintainer: $MAINTAINER
Installed-Size: $(du -sk "$DEB" | cut -f1)
Depends: libc6 (>= ${GLIBC:-2.31}), libstdc++6, libgcc-s1, libgl1, libegl1, libxkbcommon0, libfontconfig1, libdbus-1-3, libxcb-cursor0, libpulse0
Description: A local studio for platform content, images, video, games and code
 ELI Creation Station makes posts, images, videos, games and code on this
 machine, with ELI beside you on the project. Every output's models and
 licences are recorded, and AI output is marked. Includes the desktop
 application and the command line.
CONTROL
  find "$DEB" -type d -exec chmod 755 {} +
  find "$DEB/usr/share" -type f -exec chmod 644 {} +
  dpkg-deb --build --root-owner-group "$DEB" "$OUT/eli-creation_${VERSION}_${DEB_ARCH}.deb" >/dev/null
fi

echo "==> AppImage"
# One file that runs without installing. appimagetool is taken from $APPIMAGETOOL, the PATH, or
# build/tools; if it is nowhere, it is downloaded from the AppImage project (set NO_DOWNLOAD=1 to
# forbid that and skip the AppImage).
TOOL="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
[ -n "$TOOL" ] || TOOL="build/tools/appimagetool"
if [ ! -x "$TOOL" ] && [ -z "${NO_DOWNLOAD:-}" ]; then
  mkdir -p build/tools
  curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
  chmod 755 "$TOOL"
fi
if [ -x "$TOOL" ]; then
  APPDIR="build/AppDir"
  rm -rf "$APPDIR"
  mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/metainfo"
  cp -a "$STAGE" "$APPDIR/usr/lib/eli-creation"
  cp packaging/linux/AppRun "$APPDIR/AppRun"
  chmod 755 "$APPDIR/AppRun"
  cp src/eli_creation/gui/assets/eli_creation_256.png "$APPDIR/eli-creation.png"
  ln -s eli-creation.png "$APPDIR/.DirIcon"
  sed -e 's|^Exec=.*|Exec=AppRun|' -e 's|^Icon=.*|Icon=eli-creation|' -e '/^Path=/d' \
    packaging/eli-creation.desktop > "$APPDIR/eli-creation.desktop"
  sed -e "s/@VERSION@/$VERSION/g" -e "s/@DATE@/$(date -u +%Y-%m-%d)/g" \
    packaging/linux/creation.eli.desktop.appdata.xml > "$APPDIR/usr/share/metainfo/creation.eli.desktop.appdata.xml"
  rm -f "$OUT/$NAME.AppImage"
  ARCH="$ARCH" VERSION="$VERSION" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT/$NAME.AppImage" >/dev/null 2>&1 \
    || ARCH="$ARCH" VERSION="$VERSION" "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT/$NAME.AppImage"
  chmod 755 "$OUT/$NAME.AppImage"
  "$OUT/$NAME.AppImage" --appimage-extract-and-run --version >/dev/null
else
  echo "    appimagetool not available: AppImage skipped" >&2
fi

(cd "$OUT" && sha256sum -- * | grep -v ' SHA256SUMS$' > SHA256SUMS)
echo "==> done"
ls -lh "$OUT"
