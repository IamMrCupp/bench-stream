# bench-stream

The small stuff that keeps the repair bench's stream running — OBS helpers, the services that run them, and the udev rules that put the cameras back the way they were after a replug.

None of it is big enough for a repo of its own, and all of it used to live only on the bench. **Now it lives here, and the bench gets it from here.**

## What's in it

| Piece | What it does | Runs as |
|---|---|---|
| [`obsctl`](bin/obsctl) | Send one obs-websocket request to the OBS on this machine, or save a screenshot of a source. `obsctl GetStats`, `obsctl shot` | Command |
| [`obs-golive`](bin/obs-golive) | When the main stream starts, wait a few seconds and start every Aitum Multistream output; when it stops, stop them. Never starts the main stream itself | `obs-golive.service` |
| [`obs-micwatch`](bin/obs-micwatch) | When the DJI Mic receiver drops off USB and comes back, PipeWire gives it a new source and OBS stays attached to nothing. This notices and re-applies the input's device | `obs-micwatch.service` |
| [`obs-sceneswitch`](bin/obs-sceneswitch) | Watches the overhead camera and switches to the scope scene when the scope arm swings over the work, back when it's parked. Needs calibrating first — `obs-sceneswitch calibrate in` / `parked` | `obs-sceneswitch.service` |
| [`pixy-tune`](bin/pixy-tune) | Manual exposure and white balance for the EMEET PIXY, which forgets both on replug | udev, on plug-in |
| [`pixy-track`](bin/pixy-track) | The PIXY's AI tracking on, off or status, over its vendor HID interface | udev, on plug-in |
| [`multichat.service`](systemd/user/multichat.service) | Runs the merged Twitch + YouTube chat overlay from [IamMrCupp/megarohas_multichat](https://github.com/IamMrCupp/megarohas_multichat), checked out at `~/.local/share/multichat`. The code lives in that fork, not here | User service |
| [`udev/`](udev) | Keep the PIXY awake, re-tune it on plug-in, and keep the host off the thermal camera's storage gadget | udev |

Every OBS helper reads the websocket port and password from OBS's own config. Nothing here stores or prints the password.

The settings each one takes (input names, scene names, delays) are at the top of the script, and the units set the ones the bench needs.

## Install

On the bench (Ubuntu, OBS with obs-websocket on):

```sh
sudo apt install python3-websockets python3-pil pulseaudio-utils v4l-utils
git clone https://github.com/IamMrCupp/bench-stream ~/Code/bench-stream
cd ~/Code/bench-stream

./install.sh --diff          # what would change — run this first on a bench that already has them
./install.sh                 # scripts and user units
sudo ./install.sh --system   # pixy-* and the udev rules
systemctl --user enable --now obs-golive obs-micwatch obs-sceneswitch
```

`install.sh` copies and reloads — it never starts or restarts a service, so a change goes live when you restart it, not when you pull. The multichat unit also needs the fork checked out at `~/.local/share/multichat` and Node.

`obs-sceneswitch`'s calibration pictures stay in `~/.local/share/scene-switch` on the bench. They're frames of the bench camera, so they don't belong in a public repo.

## Tests

The OBS helpers are tested against a fake OBS — the tests never touch a real one.

```sh
pip install websockets pillow
python3 tests/test_obs_golive.py
python3 tests/test_obs_micwatch.py
python3 tests/test_obs_sceneswitch.py
```

CI runs the same three on every pull request.

## Credit

`pixy-track`'s HID report layout comes from what the PixyPilot and omarchy-emeet-pixy projects worked out about the PIXY, checked against this camera.

## License

[AGPL-3.0-or-later](LICENSE), same as the rest of the bench tools. Contributions: see [CONTRIBUTING](CONTRIBUTING.md).
