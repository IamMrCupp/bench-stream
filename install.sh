#!/bin/sh
# Put bench-stream's scripts, units and udev rules where the bench runs them.
#
#   ./install.sh               user part: scripts -> ~/.local/bin, units -> ~/.config/systemd/user
#   sudo ./install.sh --system system part: pixy-* -> /usr/local/bin, rules -> /etc/udev/rules.d
#   ./install.sh --diff        show what differs between this checkout and what's installed
#
# It copies files and reloads systemd / udev. It never enables, starts or
# restarts a service: do that yourself once you've looked at the change.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
USER_SCRIPTS="obsctl obs-golive obs-micwatch obs-sceneswitch"
SYSTEM_SCRIPTS="pixy-tune pixy-track"
BIN="$HOME/.local/bin"
UNITS="$HOME/.config/systemd/user"
SBIN=/usr/local/bin
RULES=/etc/udev/rules.d

pairs() {  # "source target" per line, for the part asked for
    case "$1" in
    user)
        for s in $USER_SCRIPTS; do echo "$HERE/bin/$s $BIN/$s"; done
        for u in "$HERE"/systemd/user/*.service; do echo "$u $UNITS/$(basename "$u")"; done
        ;;
    system)
        for s in $SYSTEM_SCRIPTS; do echo "$HERE/bin/$s $SBIN/$s"; done
        for r in "$HERE"/udev/*.rules; do echo "$r $RULES/$(basename "$r")"; done
        ;;
    esac
}

case "${1:-}" in
--diff)
    { pairs user; pairs system; } | while read -r src dst; do
        if [ ! -e "$dst" ]; then
            echo "not installed: $dst"
        elif ! cmp -s "$src" "$dst"; then
            echo "differs:       $dst"
            diff -u "$dst" "$src" || true
        fi
    done
    ;;
--system)
    [ "$(id -u)" -eq 0 ] || { echo "install.sh --system needs root (sudo)" >&2; exit 1; }
    pairs system | while read -r src dst; do
        case "$dst" in *.rules) mode=0644 ;; *) mode=0755 ;; esac
        install -D -m "$mode" "$src" "$dst" && echo "installed $dst"
    done
    udevadm control --reload
    echo "udev rules reloaded. They apply the next time each device appears (replug or reboot)."
    ;;
"")
    [ "$(id -u)" -ne 0 ] || { echo "run the user part as yourself, not root" >&2; exit 1; }
    pairs user | while read -r src dst; do
        case "$dst" in *.service) mode=0644 ;; *) mode=0755 ;; esac
        install -D -m "$mode" "$src" "$dst" && echo "installed $dst"
    done
    systemctl --user daemon-reload
    echo "systemd reloaded. Restart a changed service with: systemctl --user restart <name>"
    ;;
*)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
