# bench-stream

The small stuff that keeps the repair bench's stream running — OBS helpers, the services that run them, and the udev rules that put the cameras back the way they were after a replug.

None of it is big enough for a repo of its own, and all of it used to live only on the bench. **Now it lives here, and the bench gets it from here.**

## What's in it

| Piece | What it does | Runs as |
|---|---|---|
| [`obsctl`](bin/obsctl) | Send one obs-websocket request to the OBS on this machine, or save a screenshot of a source. `obsctl GetStats`, `obsctl shot` | Command |
| [`obs-golive`](bin/obs-golive) | When the main stream starts, wait a few seconds and start every Aitum Multistream output; when it stops, stop them. Never starts the main stream itself | `obs-golive.service` |
| [`obs-micwatch`](bin/obs-micwatch) | When the DJI Mic receiver drops off USB and comes back, PipeWire gives it a new source and OBS stays attached to nothing. This notices and re-applies the input's device. If the receiver comes back with no audio interface at all, it logs that it needs a replug. While linked, it logs when the mic has sent nothing but digital silence for 15 s — the transmitter's wireless link is down | `obs-micwatch.service` |
| [`obs-sceneswitch`](bin/obs-sceneswitch) | Watches the overhead camera and switches to the scope scene when the scope arm swings over the work, back when it's parked. Also follows window focus: PulseView, OpenBoardView and Burnwright each get their scene, the HUD goes back to the cameras. The arm needs calibrating first — `obs-sceneswitch calibrate in` / `parked` | `obs-sceneswitch.service` |
| [`mevo-relay`](bin/mevo-relay) | Passes the Mevo's SRT feed on to OBS with the audio taken out. The Mevo always sends an audio track, even with every mic off in its app, and its drift pushes OBS's audio buffering to the 960 ms maximum. The video is copied, not re-encoded, to `udp://127.0.0.1:4202` | `mevo-relay.service` |
| [`kde/kwin`](kde/kwin) | A KWin script that tells `obs-sceneswitch` which app just got focus. OBS runs under XWayland and can't see native Wayland windows; KWin can | KWin script |
| [`kde/applications`](kde/applications) | Meta+1 to Meta+7 pick a scene by hand: Overhead, Scope, Chip Programmer, Board View, Logic Analyzer, Terminal, Browser | KDE global shortcuts |
| [`pixy-tune`](bin/pixy-tune) | Manual exposure and white balance for the EMEET PIXY, which forgets both on replug | udev, on plug-in |
| [`pixy-track`](bin/pixy-track) | The PIXY's AI tracking on, off or status, over its vendor HID interface | udev, on plug-in |
| [`multichat.service`](systemd/user/multichat.service) | Runs the merged Twitch + YouTube chat overlay from [IamMrCupp/megarohas_multichat](https://github.com/IamMrCupp/megarohas_multichat), checked out at `~/.local/share/multichat`. The code lives in that fork, not here | User service |
| [`udev/`](udev) | Keep the PIXY awake, re-tune it on plug-in, and keep the host off the thermal camera's storage gadget | udev |

Every OBS helper reads the websocket port and password from OBS's own config. Nothing here stores or prints the password.

The settings each one takes (input names, scene names, delays) are at the top of the script, and the units set the ones the bench needs.

## Install

On the bench (Ubuntu, OBS with obs-websocket on):

```sh
sudo apt install python3-websockets python3-pil python3-dbus python3-gi pulseaudio-utils v4l-utils
git clone https://github.com/IamMrCupp/bench-stream ~/Code/bench-stream
cd ~/Code/bench-stream

./install.sh --diff          # what would change — run this first on a bench that already has them
./install.sh                 # scripts and user units
sudo ./install.sh --system   # pixy-* and the udev rules
systemctl --user enable --now obs-golive obs-micwatch obs-sceneswitch mevo-relay
```

`install.sh` copies and reloads — it never starts or restarts a service, so a change goes live when you restart it, not when you pull. The multichat unit also needs the fork checked out at `~/.local/share/multichat` and Node.

### The Mevo through the relay

The Mevo takes one SRT connection at a time, so OBS has to stop calling it before the relay can. Point the "Mevo SRT" source at the relay; its name stays the same, so `obs-sceneswitch` keeps working:

```sh
obsctl SetInputSettings '{"inputName":"Mevo SRT","inputSettings":{"input":"udp://127.0.0.1:4202?timeout=15000000&overrun_nonfatal=1"}}'
```

Then restart OBS once. OBS never lowers its audio buffering while it runs, so the second it already built up only goes away on a restart. The Mevo's address is in `mevo-relay.service`. The 15 s timeout is longer than the gap while the relay restarts, so OBS keeps its connection through a relay restart. While the Mevo is off, the unit backs off to one try every 30 s.

### Scene switching off focus, and the scene shortcuts

The KWin script installs disabled. Turn it on once:

```sh
kwriteconfig6 --file kwinrc --group Plugins --key obs-sceneswitch-focusEnabled true
qdbus6 org.kde.KWin /KWin reconfigure
```

After an update to the script, turn it off and on again the same way (`false`, reconfigure, `true`, reconfigure) so KWin loads the new one.

| Window gets focus | Scene |
|---|---|
| PulseView | Logic Analyzer |
| OpenBoardView | Board View |
| Burnwright | Chip Programmer |
| The HUD | Scope Camera with the arm in, Overhead Camera otherwise |
| Anything else | No change |

It switches only when focus moves to a different app, so a scene picked by hand stays until you click into another one, OBS and system dialogs included. If OBS wasn't running when focus moved, click away and back. There's no idle timer. For the first few seconds after the service starts, and until the arm is calibrated, the HUD goes to Overhead Camera. The arm still switches only between Overhead and Scope, so it never pulls you off an app scene. Change the list with `SCENESWITCH_APPS` and `SCENESWITCH_HUD` in the unit (see the top of the script).

Terminal and Browser are shortcut-only on purpose: what's on those screens is never put on stream by clicking into a window.

The shortcuts register when `install.sh` rebuilds KDE's app list. Plasma ships Meta+1 to Meta+9 bound to the task manager's entries, and a shortcut whose key is taken registers with no key at all. Free 1 to 7 before the first `./install.sh`:

```sh
python3 - <<'PY'
import dbus
ka = dbus.Interface(dbus.SessionBus().get_object("org.kde.kglobalaccel", "/kglobalaccel"), "org.kde.KGlobalAccel")
for n in range(1, 8):
    ka.setForeignShortcutKeys(["plasmashell", f"activate task manager entry {n}", "plasmashell", ""], dbus.Array([], signature="(ai)"))
PY
```

If you installed first, delete `~/.local/share/applications/obs-scene-*.desktop`, run `kbuildsycoca6`, then free the keys and run `./install.sh` again.

A shortcut for a scene OBS doesn't have yet does nothing.

`obs-sceneswitch`'s calibration pictures stay in `~/.local/share/scene-switch` on the bench. They're frames of the bench camera, so they don't belong in a public repo.

## Tests

The OBS helpers are tested against a fake OBS — the tests never touch a real one.

```sh
pip install websockets pillow
python3 tests/test_obs_golive.py
python3 tests/test_obs_micwatch.py
python3 tests/test_obs_sceneswitch.py
python3 tests/test_mevo_relay.py   # needs ffmpeg; the SRT test runs where ffmpeg has SRT, as on the bench
```

CI runs all four on every pull request.

## Credit

`pixy-track`'s HID report layout comes from what the PixyPilot and omarchy-emeet-pixy projects worked out about the PIXY, checked against this camera.

## Support

If it's earned a spot on your bench and you'd like to throw a coffee my way:

- [Ko-fi](https://ko-fi.com/IamMrCupp)
- [Buy Me a Coffee](https://buymeacoffee.com/IamMrCupp)

No pressure — it stays open source either way.

## License

[AGPL-3.0-or-later](LICENSE), same as the rest of the bench tools. Contributions: see [CONTRIBUTING](CONTRIBUTING.md).
