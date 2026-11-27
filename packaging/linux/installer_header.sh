#!/bin/sh
# Adapted from ELI_Legal: packaging/linux/installer_header.sh @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
# ELI Creation Station @VERSION@ - installer for Linux (@ARCH@).
#
#   sh ELI_Creation_Station-@VERSION@-linux-@ARCH@.run              install for the current user
#   sh ELI_Creation_Station-@VERSION@-linux-@ARCH@.run --system     install for everyone (as root)
#   sh ELI_Creation_Station-@VERSION@-linux-@ARCH@.run --uninstall  remove the program (never your data)
#   sh ELI_Creation_Station-@VERSION@-linux-@ARCH@.run --verify     check this file is intact, install nothing
#
# The program is everything after the line __PAYLOAD_BELOW__. Its SHA-256 is recorded here and
# checked before anything is unpacked.
set -eu

VERSION="@VERSION@"
SHA256="@SHA256@"
MARK=".eli-creation-program-folder"
PREFIX="${HOME}/.local/opt/eli-creation"
BIN="${HOME}/.local/bin"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
MODE="install"
DESKTOP=1

say() { printf '%s\n' "$*"; }
fail() { printf 'eli-creation installer: %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) [ $# -ge 2 ] || fail "--prefix needs a folder"; PREFIX="$2"; shift 2 ;;
    --bin-dir) [ $# -ge 2 ] || fail "--bin-dir needs a folder"; BIN="$2"; shift 2 ;;
    --system) PREFIX="/opt/eli-creation"; BIN="/usr/local/bin"; SHARE="/usr/share"; shift ;;
    --no-desktop) DESKTOP=0; shift ;;
    --uninstall) MODE="uninstall"; shift ;;
    --verify) MODE="verify"; shift ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "unknown option: $1 (try --help)" ;;
  esac
done

APP="$PREFIX/app"
ENTRY="$SHARE/applications/eli-creation.desktop"
ICON="$SHARE/icons/hicolor/256x256/apps/eli-creation.png"

remove_program() {
  # Only ever delete a folder this installer created.
  if [ -e "$APP" ]; then
    [ -f "$APP/$MARK" ] || fail "$APP exists but was not created by this installer; not touching it"
    rm -rf "$APP"
  fi
}

if [ "$MODE" = "uninstall" ]; then
  # ELI v3's record of this copy goes with it; a record of another copy is left alone.
  [ -x "$APP/eli-creation" ] && "$APP/eli-creation" bundle unregister --this-copy >/dev/null 2>&1 || true
  remove_program
  for name in eli-creation eli-creation-gui; do
    if [ -f "$BIN/$name" ] && grep -q "ELI Creation Station launcher" "$BIN/$name" 2>/dev/null; then rm -f "$BIN/$name"; fi
  done
  rm -f "$ENTRY" "$ICON"
  rmdir "$PREFIX" 2>/dev/null || true
  say "ELI Creation Station has been removed."
  say "Your projects, outputs, models and provenance ledger were NOT removed. They are in:"
  say "  ${XDG_DATA_HOME:-$HOME/.local/share}/eli-creation"
  exit 0
fi

LINE=$(awk '/^__PAYLOAD_BELOW__$/ { print NR + 1; exit 0 }' "$0")
[ -n "$LINE" ] || fail "this file is incomplete"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is needed to check this file"
FOUND=$(tail -n +"$LINE" "$0" | sha256sum | cut -d' ' -f1)
[ "$FOUND" = "$SHA256" ] || fail "this file is damaged or has been altered (checksum mismatch); download it again"
if [ "$MODE" = "verify" ]; then say "ELI Creation Station $VERSION: this installer is intact ($SHA256)."; exit 0; fi

case "$(uname -m)" in @ARCH@) ;; *) fail "this installer is for @ARCH@ machines; this one is $(uname -m)" ;; esac
mkdir -p "$PREFIX" "$BIN" || fail "cannot write to $PREFIX or $BIN (for a system-wide install use --system as root)"

NEW="$PREFIX/app.new.$$"
rm -rf "$NEW"; mkdir -p "$NEW"
trap 'rm -rf "$NEW"' EXIT
say "Unpacking ELI Creation Station $VERSION to $APP ..."
tail -n +"$LINE" "$0" | tar -xzf - -C "$NEW"
[ -x "$NEW/eli-creation/eli-creation" ] || fail "the program did not unpack correctly"
"$NEW/eli-creation/eli-creation" --help >/dev/null 2>&1 || fail "the program does not run on this system (it needs glibc @GLIBC@ or newer)"
remove_program
mv "$NEW/eli-creation" "$APP"
: > "$APP/$MARK"

for name in eli-creation eli-creation-gui; do
  printf '#!/bin/sh\n# ELI Creation Station launcher (created by the installer)\nexec "%s/%s" "$@"\n' "$APP" "$name" > "$BIN/$name"
  chmod 755 "$BIN/$name"
done

if [ "$DESKTOP" = 1 ]; then
  mkdir -p "$(dirname "$ENTRY")" "$(dirname "$ICON")"
  cp "$APP/_internal/eli_creation/gui/assets/eli_creation_256.png" "$ICON"
  cat > "$ENTRY" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ELI Creation Station
GenericName=Creative studio
Comment=Platform content, images, video, games and code, with ELI beside you
Exec=$APP/eli-creation-gui
Icon=$ICON
Terminal=false
Categories=Graphics;AudioVideo;Development;
StartupWMClass=ELI Creation Station
DESKTOP
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$ENTRY")" >/dev/null 2>&1 || true
fi

# ELI v3, if it is on this machine, opens this copy from its start-up choice and Bundles menu.
# For the current user only: a system-wide install registers when each user first starts it.
if [ "$BIN" != "/usr/local/bin" ]; then
  "$APP/eli-creation" bundle register --if-eli-v3 >/dev/null 2>&1 || true
fi

say ""
say "ELI Creation Station $VERSION is installed."
say "  Desktop application : eli-creation-gui   (also in your applications menu)"
say "  Command line        : eli-creation --help"
say "  Server              : eli-creation serve --help"
say "  Your data           : ${XDG_DATA_HOME:-$HOME/.local/share}/eli-creation  (kept if you uninstall)"
say "  Documentation       : $APP/_internal/README.md"
case ":$PATH:" in *":$BIN:"*) ;; *) say "  Note: $BIN is not on your PATH; add it, or run $BIN/eli-creation directly." ;; esac
say "To remove it later:  sh $(basename "$0") --uninstall"
exit 0
__PAYLOAD_BELOW__
