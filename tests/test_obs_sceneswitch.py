#!/usr/bin/env python3
"""Tests for obs-sceneswitch against a fake OBS. Run: python3 tests/test_obs_sceneswitch.py [path/to/obs-sceneswitch]

The fake serves a made-up overhead picture with a bright "scope head" drawn either
over the work or parked at the top left, plus some noise so no two frames match
exactly. Window focus is fed in the way the D-Bus listener would hand it over.
It never touches the real OBS or the session bus.
"""
import asyncio, base64, configparser, importlib.machinery, importlib.util, inspect, io, json, os, random, re, shlex, shutil, sys, tempfile

import websockets
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "bin", "obs-sceneswitch")
KDE = os.path.join(HERE, "..", "kde")
SCENES = {"Overhead Camera", "Scope Camera", "Chip Programmer", "Board View", "Logic Analyzer", "Some Other Scene"}


def picture(position, seed=0, hand=False, spot=(45, 40), under=None):
    if position == "blocked":  # someone leaning over the bench: looks like neither reference
        im = Image.new("RGB", (160, 90), (90, 70, 60))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue() + bytes([seed % 251])  # trailing byte is ignored by the decoder

    rnd = random.Random(seed)
    im = Image.new("RGB", (160, 90), (40, 110, 170))  # the blue mat
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 160, 25), fill=(30, 30, 30))  # tool racks along the back
    if under:  # whatever is on the mat: a board, a chassis
        d.rectangle((30, 28, 95, 52), fill=under)
    if position == "in":
        x, y = spot
        d.ellipse((x, y, x + 42, y + 36), fill=(235, 235, 230))  # scope head over the mat, wherever it landed
        d.rectangle((x + 42, y + 14, 160, y + 20), fill=(235, 235, 230))  # the boom back to its post
    else:
        d.ellipse((125, 20, 175, 60), fill=(235, 235, 230))  # parked: swung off to the right of the mat
    if hand:
        d.ellipse((60, 60, 80, 85), fill=(200, 150, 120))
    px = im.load()
    for _ in range(300):  # sensor noise
        x, y = rnd.randrange(160), rnd.randrange(90)
        r, g, b = px[x, y]
        n = rnd.randint(-8, 8)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class FakeObs:
    def __init__(self, position="parked", scene="Overhead Camera"):
        self.position, self.scene = position, scene
        self.hand = False
        self.spot, self.under = (45, 40), None
        self.frozen = None  # bytes to serve unchanged, to imitate a frozen picture
        self.switches = []
        self.looks = 0
        self.clients = set()
        self.scenes = set(SCENES)  # SetCurrentProgramScene to anything else fails, as OBS does
        self.report = None  # what the service gave its focus listener

    def focus(self, resource_class, desktop_file=""):
        """A window gets focus, as the KWin script reports it."""
        self.report((resource_class, desktop_file))

    def listen(self, report):
        self.report = report

    async def handler(self, ws):
        await ws.send(json.dumps({"op": 0, "d": {"rpcVersion": 1}}))
        await ws.recv()
        await ws.send(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
        self.clients.add(ws)
        try:
            async for raw in ws:
                d = json.loads(raw)["d"]
                kind, data = d["requestType"], d.get("requestData") or {}
                ok, resp = True, {}
                if kind == "GetSourceScreenshot":
                    self.looks += 1
                    img = self.frozen or picture(self.position, seed=self.looks, hand=self.hand, spot=self.spot, under=self.under)
                    resp = {"imageData": "data:image/png;base64," + base64.b64encode(img).decode()}
                elif kind == "GetCurrentProgramScene":
                    resp = {"currentProgramSceneName": self.scene}
                elif kind == "SetCurrentProgramScene":
                    if data["sceneName"] in self.scenes:
                        self.scene = data["sceneName"]
                        self.switches.append(self.scene)
                    else:
                        ok = False
                else:
                    ok = False
                await ws.send(json.dumps({"op": 7, "d": {"requestType": kind, "requestId": d["requestId"],
                                                           "requestStatus": {"result": ok, "code": 100},
                                                           "responseData": resp}}))
        finally:
            self.clients.discard(ws)


def load(conf, data_dir, **env):
    for k in [k for k in os.environ if k.startswith("SCENESWITCH_")]:
        del os.environ[k]  # nothing carried over from the test before
    os.environ.update(SCENESWITCH_CONF=conf, SCENESWITCH_DIR=data_dir, SCENESWITCH_INTERVAL="0.02",
                      SCENESWITCH_RETRY="0.05", SCENESWITCH_HOLD="3", SCENESWITCH_STALE="1000",
                      SCENESWITCH_MAT="0.04,0.03,0.625,0.95")
    os.environ.update(env)
    loader = importlib.machinery.SourceFileLoader("obs_sceneswitch", SCRIPT)
    spec = importlib.util.spec_from_loader("obs_sceneswitch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod.log = lambda *a: None
    return mod


async def until(cond, timeout=4.0):
    end = asyncio.get_event_loop().time() + timeout
    while not cond():
        if asyncio.get_event_loop().time() > end:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.01)


async def harness(fake, body, calibrate=("in", "parked"), **env):
    async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        data_dir = tempfile.mkdtemp()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"server_port": port, "server_password": ""}, f)
        mod = load(f.name, data_dir, **env)
        start_pos = fake.position
        for pos in calibrate:
            label, shown = pos if isinstance(pos, tuple) else (pos, pos)  # (save as, what the camera shows)
            fake.position = shown
            assert await mod.cmd_calibrate(label) == 0
        fake.position = start_pos
        task = asyncio.create_task(mod.cmd_run(listen=fake.listen))
        try:
            await body(fake, mod)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            os.unlink(f.name)
            shutil.rmtree(data_dir, ignore_errors=True)


async def settle(fake, looks=8):
    n = fake.looks
    await until(lambda: fake.looks >= n + looks)


async def test_swinging_the_arm_in_switches_to_the_scope_scene():
    async def body(fake, mod):
        await settle(fake)
        assert fake.switches == []
        fake.position = "in"
        await until(lambda: fake.switches == ["Scope Camera"])
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_parking_the_arm_switches_back_to_overhead():
    async def body(fake, mod):
        await settle(fake)
        fake.position = "parked"
        await until(lambda: fake.switches == ["Overhead Camera"])
    await harness(FakeObs("in", "Scope Camera"), body)


async def test_starting_up_never_switches_by_itself():
    async def body(fake, mod):
        await settle(fake, 15)
        assert fake.switches == [], fake.switches
    # arm is in, but the overhead scene is live: that was the user's choice before we started
    await harness(FakeObs("in", "Overhead Camera"), body)


async def test_a_scene_picked_by_hand_is_left_alone():
    async def body(fake, mod):
        await settle(fake)
        fake.scene = "Some Other Scene"
        fake.position = "in"
        await settle(fake, 15)
        assert fake.switches == [], fake.switches
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_a_hand_in_shot_does_not_flip_the_scene():
    async def body(fake, mod):
        await settle(fake)
        fake.hand = True
        await settle(fake, 15)
        assert fake.switches == [], fake.switches
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_a_brief_glimpse_is_not_enough():
    async def body(fake, mod):
        await settle(fake)
        n = fake.looks
        fake.position = "in"
        await until(lambda: fake.looks >= n + 1)
        fake.position = "parked"  # back before three looks agreed (hold is 50 here)
        await settle(fake, 15)
        assert fake.switches == [], fake.switches
    await harness(FakeObs("parked", "Overhead Camera"), body, SCENESWITCH_HOLD="50")


async def test_without_both_references_it_does_nothing():
    async def body(fake, mod):
        await asyncio.sleep(0.4)
        fake.position = "in"
        await asyncio.sleep(0.4)
        assert fake.switches == [] and fake.looks == 1, (fake.switches, fake.looks)  # the one look was the calibration
    await harness(FakeObs("parked", "Overhead Camera"), body, calibrate=("parked",))


async def test_a_frozen_picture_is_not_trusted():
    async def body(fake, mod):
        await settle(fake)
        fake.frozen = picture("in", seed=1)  # the same bytes every look, as a stalled source would give
        await settle(fake, 20)
        assert fake.switches == [], fake.switches
    await harness(FakeObs("parked", "Overhead Camera"), body, SCENESWITCH_STALE="2", SCENESWITCH_HOLD="5")


async def test_a_picture_that_matches_neither_position_changes_nothing():
    async def body(fake, mod):
        await settle(fake)
        fake.position = "blocked"
        await settle(fake, 20)
        assert fake.switches == [], fake.switches
    await harness(FakeObs("in", "Scope Camera"), body)


async def test_the_arm_landing_somewhere_else_still_switches():
    for spot in ((10, 30), (40, 8), (55, 50), (20, 45)):
        async def body(fake, mod):
            await settle(fake)
            fake.spot = spot
            fake.position = "in"
            await until(lambda: fake.switches == ["Scope Camera"])
        await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_what_is_on_the_mat_does_not_matter():
    for under in ((20, 120, 60), (25, 25, 25), (150, 60, 40)):  # a green board, a black chassis, a copper thing
        async def body(fake, mod):
            fake.under = under
            await settle(fake, 15)
            assert fake.switches == [], (under, fake.switches)  # parked with it on the mat: no switch
            fake.position = "in"
            await until(lambda: fake.switches == ["Scope Camera"])
            fake.position = "parked"
            await until(lambda: fake.switches == ["Scope Camera", "Overhead Camera"])
        await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_references_that_look_alike_do_nothing():
    async def body(fake, mod):
        await asyncio.sleep(0.4)
        assert fake.switches == [] and fake.looks == 2, (fake.switches, fake.looks)  # only the two calibrations
    await harness(FakeObs("parked", "Overhead Camera"), body, calibrate=(("in", "parked"), "parked"))


def test_decider_unit():
    mod = load("/nonexistent", tempfile.mkdtemp())
    d = mod.Decider(hold=3)
    assert [d.feed(x) for x in ["parked"] * 3] == [None, None, None]  # baseline, not a change
    assert [d.feed(x) for x in ["in", "in", None, "in", "in", "in"]] == [None, None, None, None, None, "in"]
    assert [d.feed(x) for x in ["in", "parked", "parked", "parked"]] == [None, None, None, "parked"]


# ---------- window focus ----------
async def test_focusing_an_app_switches_to_its_scene():
    async def body(fake, mod):
        await settle(fake)
        fake.focus("org.sigrok.pulseview", "org.sigrok.PulseView")
        await until(lambda: fake.switches == ["Logic Analyzer"])
        fake.focus("openboardview")
        await until(lambda: fake.switches == ["Logic Analyzer", "Board View"])
        fake.focus("Burnwright", "burnwright")
        await until(lambda: fake.switches == ["Logic Analyzer", "Board View", "Chip Programmer"])
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_focusing_the_hud_goes_back_to_the_camera_the_arm_says():
    async def body(fake, mod):
        await settle(fake)
        fake.focus("openboardview")
        await until(lambda: fake.scene == "Board View")
        fake.focus("benchhud")
        await until(lambda: fake.scene == "Overhead Camera")
        fake.focus("openboardview")
        await until(lambda: fake.scene == "Board View")
        fake.position = "in"  # the arm swings in while an app scene is live: the arm leaves it alone
        await settle(fake, 15)
        assert fake.scene == "Board View", fake.switches
        fake.focus("benchhud")
        await until(lambda: fake.scene == "Scope Camera")
        assert fake.switches == ["Board View", "Overhead Camera", "Board View", "Scope Camera"], fake.switches
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_other_windows_change_nothing():
    async def body(fake, mod):
        await settle(fake)
        for cls in ("google-chrome", "org.kde.konsole", "obs", "Claude", "", "systemsettings"):
            fake.focus(cls)
        fake.focus("openboardview")  # handled in order: once this lands, the ones before did nothing
        await until(lambda: fake.switches == ["Board View"])
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_a_scene_picked_by_hand_stays_until_focus_moves_to_another_app():
    async def body(fake, mod):
        await settle(fake)
        fake.focus("Burnwright", "burnwright")
        await until(lambda: fake.switches == ["Chip Programmer"])
        fake.scene = "Some Other Scene"  # picked by hand, Burnwright still focused
        fake.focus("Burnwright", "burnwright")  # one of its dialogs, or it again: same app
        fake.focus("burnwright", "")
        await asyncio.sleep(0.2)
        assert fake.scene == "Some Other Scene", fake.switches
        fake.focus("google-chrome")  # away and back is a change
        fake.focus("Burnwright", "burnwright")
        await until(lambda: fake.switches == ["Chip Programmer", "Chip Programmer"])
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_focus_does_not_fight_the_arm():
    async def body(fake, mod):
        await settle(fake)
        fake.position = "in"
        await until(lambda: fake.switches == ["Scope Camera"])
        fake.focus("org.sigrok.pulseview")
        await until(lambda: fake.scene == "Logic Analyzer")
        fake.position = "parked"  # arm parked while the analyzer is up: nothing
        await settle(fake, 15)
        assert fake.scene == "Logic Analyzer", fake.switches
        fake.focus("benchhud")
        await until(lambda: fake.scene == "Overhead Camera")
        await settle(fake, 15)
        assert fake.switches == ["Scope Camera", "Logic Analyzer", "Overhead Camera"], fake.switches
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_the_hud_remembers_the_arm_across_an_obs_reconnect():
    async def body(fake, mod):
        await settle(fake)
        fake.position = "in"
        await until(lambda: fake.switches == ["Scope Camera"])
        fake.focus("openboardview")
        await until(lambda: fake.scene == "Board View")
        n = fake.looks
        for c in list(fake.clients):
            await c.close()  # OBS restarts: the arm watcher starts over with a fresh baseline
        await until(lambda: fake.looks > n)
        fake.focus("benchhud")
        await until(lambda: fake.scene == "Scope Camera")
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_focus_works_before_the_arm_is_calibrated():
    async def body(fake, mod):
        await asyncio.sleep(0.2)
        fake.focus("openboardview")
        await until(lambda: fake.switches == ["Board View"])
        fake.focus("benchhud")  # the arm's position isn't known: overhead
        await until(lambda: fake.switches == ["Board View", "Overhead Camera"])
        assert fake.looks == 0
    await harness(FakeObs("in", "Scope Camera"), body, calibrate=())


async def test_a_missing_scene_is_survived():
    async def body(fake, mod):
        await settle(fake)
        fake.scenes.discard("Board View")
        fake.focus("openboardview")  # fails in OBS; the next one must still work
        fake.focus("org.sigrok.pulseview")
        await until(lambda: fake.switches == ["Logic Analyzer"])
    await harness(FakeObs("parked", "Overhead Camera"), body)


async def test_the_app_list_comes_from_the_environment():
    async def body(fake, mod):
        await settle(fake)
        fake.focus("org.sigrok.pulseview")  # not in this list
        fake.focus("Kicad", "org.kde.kicad")
        await until(lambda: fake.switches == ["Some Other Scene"])
        fake.focus("benchhud")  # not the HUD here
        fake.focus("myhud")
        await until(lambda: fake.switches == ["Some Other Scene", "Overhead Camera"])
    await harness(FakeObs("parked", "Overhead Camera"), body,
                  SCENESWITCH_APPS="kicad=Some Other Scene", SCENESWITCH_HUD="MyHUD")


def test_focus_unit():
    mod = load("/nonexistent", tempfile.mkdtemp())
    assert mod.parse_apps(" a = One ,b=Two Words,broken,=x,c=") == {"a": "One", "b": "Two Words"}
    f = mod.Focus({"burnwright": "Chip Programmer"}, "benchhud")
    assert f.feed("", "") is None
    assert f.feed("Burnwright", "") == "Chip Programmer"
    assert f.feed("burnwright", "burnwright") is None  # same app
    assert f.feed("x-weird", "burnwright") == "Chip Programmer"  # matched on desktopFileName
    assert f.feed("BenchHUD") is mod.HUD_TARGET
    assert f.feed("benchhud") is None
    assert f.feed("konsole") is None and f.last == "konsole"


def test_the_default_apps_never_include_the_manual_only_scenes():
    mod = load("/nonexistent", tempfile.mkdtemp())
    scenes = set(mod.parse_apps(mod.APPS).values())
    assert scenes == {"Logic Analyzer", "Board View", "Chip Programmer"}, scenes


def test_the_kwin_script_calls_the_name_the_service_owns():
    mod = load("/nonexistent", tempfile.mkdtemp())
    js = open(os.path.join(KDE, "kwin", "obs-sceneswitch-focus", "contents", "code", "main.js")).read()
    call = re.search(r'callDBus\("([^"]+)", "([^"]+)", "([^"]+)",\s*"(\w+)"', js)
    assert call and call.groups() == (mod.BUS_NAME, mod.BUS_PATH, mod.BUS_NAME, "Focus"), call
    assert "workspace.windowActivated.connect" in js
    meta = json.load(open(os.path.join(KDE, "kwin", "obs-sceneswitch-focus", "metadata.json")))
    assert meta["KPlugin"]["Id"] == "obs-sceneswitch-focus" and meta["X-Plasma-API"] == "javascript"


def desktop_exec(value):
    """Exec= as the launcher runs it: string-unescape the value, then split it the way the
    Desktop Entry spec quotes arguments (which, for what's used here, is shell double quoting)."""
    value = re.sub(r"\\(.)", lambda m: {"s": " ", "n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), value)
    return shlex.split(value)


def test_the_scene_shortcuts():
    want = {1: "Overhead Camera", 2: "Scope Camera", 3: "Chip Programmer", 4: "Board View",
            5: "Logic Analyzer", 6: "Terminal", 7: "Browser"}
    got = {}
    folder = os.path.join(KDE, "applications")
    for name in sorted(os.listdir(folder)):
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        cp.read(os.path.join(folder, name))
        e = cp["Desktop Entry"]
        key = re.fullmatch(r"Meta\+(\d)", e["X-KDE-Shortcuts"])
        assert key, (name, e["X-KDE-Shortcuts"])
        argv = desktop_exec(e["Exec"])
        assert argv[:2] == ["obsctl", "SetCurrentProgramScene"] and len(argv) == 3, argv
        got[int(key.group(1))] = json.loads(argv[2])["sceneName"]
        assert e["NoDisplay"] == "true" and e["Type"] == "Application"
        assert e["StartupNotify"] == "false"  # obsctl opens no window: no busy cursor waiting for one
    assert got == want, got


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        try:
            if inspect.iscoroutinefunction(t):
                asyncio.run(t())
            else:
                t()
            print("ok  ", name)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("FAIL", name, "::", type(e).__name__, e)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
