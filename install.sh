#!/bin/sh
# Put bench-stream's scripts, units and udev rules where the bench runs them.
#
#   ./install.sh               user part: scripts -> ~/.local/bin, units -> ~/.config/systemd/user,
#                              KDE scene shortcuts and the KWin focus script -> ~/.local/share
#   sudo ./install.sh --system system part: pixy-* -> /usr/local/bin, rules -> /etc/udev/rules.d
#   ./install.sh --diff        show what differs between this checkout and what's installed
#
# It copies files and reloads systemd / udev / KDE's app list. It never enables,
# starts or restarts a service or KWin script: do that yourself once you've
# looked at the change.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
USER_SCRIPTS="obsctl obs-golive obs-micwatch obs-sceneswitch mevo-relay mevo-watch"
SYSTEM_SCRIPTS="pixy-tune pixy-track"
BIN="$HOME/.local/bin"
UNITS="$HOME/.config/systemd/user"
APPS="$HOME/.local/share/applications"
KWIN="$HOME/.local/share/kwin/scripts"
SBIN=/usr/local/bin
RULES=/etc/udev/rules.d

pairs() {  # "source target" per line, for the part asked for
    case "$1" in
    user)
        for s in $USER_SCRIPTS; do echo "$HERE/bin/$s $BIN/$s"; done
        for u in "$HERE"/systemd/user/*.service; do echo "$u $UNITS/$(basename "$u")"; done
        for a in "$HERE"/kde/applications/*.desktop; do echo "$a $APPS/$(basename "$a")"; done
        (cd "$HERE/kde/kwin" && find . -type f | sort) | while read -r f; do
            echo "$HERE/kde/kwin/${f#./} $KWIN/${f#./}"
        done
        ;;
    system)
        for s in $SYSTEM_SCRIPTS; do echo "$HERE/bin/$s $SBIN/$s"; done
        for r in "$HERE"/udev/*.rules; do echo "$r $RULES/$(basename "$r")"; done
        ;;
    esac
}

case "${1:-}" in
--diff)
    # As yourself: under sudo, $HOME is root's and every user file looks missing.
    [ "$(id -u)" -ne 0 ] || { echo "run --diff as yourself, not root" >&2; exit 1; }
    { pairs user; pairs system; } | while read -r src dst; do
        if [ ! -e "$dst" ]; then
            echo "not installed: $dst"
        elif ! cmp -s "$src" "$dst"; then
            echo "differs:       $dst"
            diff -u "$dst" "$src" || true
        elif [ -x "$src" ] && [ ! -x "$dst" ]; then
            echo "not executable: $dst"
        fi
    done
    ;;
--system)
    [ "$(id -u)" -eq 0 ] || { echo "install.sh --system needs root (sudo)" >&2; exit 1; }
    pairs system | while read -r src dst; do
        case "$dst" in *.rules) mode=0644 ;; *) mode=0755 ;; esac
        install -D -T -m "$mode" "$src" "$dst" || exit 1
        echo "installed $dst"
    done
    udevadm control --reload
    echo "udev rules reloaded. They apply the next time each device appears (replug or reboot)."
    ;;
"")
    [ "$(id -u)" -ne 0 ] || { echo "run the user part as yourself, not root" >&2; exit 1; }
    pairs user | while read -r src dst; do
        case "$dst" in "$BIN"/*) mode=0755 ;; *) mode=0644 ;; esac
        install -D -T -m "$mode" "$src" "$dst" || exit 1
        echo "installed $dst"
    done
    systemctl --user daemon-reload
    echo "systemd reloaded. Restart a changed service with: systemctl --user restart <name>"
    if command -v kbuildsycoca6 >/dev/null 2>&1; then
        kbuildsycoca6 >/dev/null 2>&1 || true  # picks up new scene shortcuts
        echo "KDE app list rebuilt. A changed KWin script loads when you re-enable it (see README)."
    fi
    ;;
*)
    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
