#!/usr/bin/env python3
"""Tests for obs-golive against a fake OBS. Run: python3 tests/test_obs_golive.py [path/to/obs-golive]

The fake speaks just enough obs-websocket v5 (with password auth) and Aitum's
vendor requests to prove what the helper does on go-live and on stop, plus
GetSourceScreenshot for the overhead camera check. It never touches the real OBS
and never puts up a real desktop notification.
"""
import asyncio, base64, hashlib, importlib.machinery, importlib.util, json, os, sys, tempfile

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "bin", "obs-golive")
PASSWORD = "test-password"


def load(conf_path):
    os.environ.update(OBS_GOLIVE_CONF=conf_path, OBS_GOLIVE_DELAY="0.05", OBS_GOLIVE_RETRY="0.05",
                      OBS_GOLIVE_MEVO="Mevo SRT", OBS_GOLIVE_MEVO_TRIES="3", OBS_GOLIVE_MEVO_GAP="0.05")
    loader = importlib.machinery.SourceFileLoader("obs_golive", SCRIPT)
    spec = importlib.util.spec_from_loader("obs_golive", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod.log = lambda *a: None
    mod.notify = lambda *a: None
    return mod


class FakeObs:
    def __init__(self, aitum=("YouTube Output", "Kick Output"), running=(), main_live=False, mevo=("ok",)):
        self.aitum = list(aitum)
        self.running = set(running)  # aitum names currently running
        self.main_live = main_live
        self.calls = []  # (requestType, name) for start_output / stop_output
        self.authed = 0
        self.clients = set()
        self.subscriptions = None
        # What each screenshot of "Mevo SRT" does, in turn; the last one repeats.
        # "ok" renders, "dead" fails like a dead feed (702), "missing" has no such input (600).
        self.mevo = list(mevo)
        self.shots = []  # sourceName of each GetSourceScreenshot
        self.stream_requests = []  # any request that would start or stop the main stream
        self.logs, self.notes = [], []

    async def handler(self, ws):
        salt, challenge = "salt", "challenge"
        await ws.send(json.dumps({"op": 0, "d": {"rpcVersion": 1, "authentication": {"salt": salt, "challenge": challenge}}}))
        ident = json.loads(await ws.recv())["d"]
        secret = base64.b64encode(hashlib.sha256((PASSWORD + salt).encode()).digest())
        want = base64.b64encode(hashlib.sha256(secret + challenge.encode()).digest()).decode()
        if ident.get("authentication") != want:
            await ws.close(4009, "auth failed")
            return
        self.authed += 1
        self.subscriptions = ident.get("eventSubscriptions")
        await ws.send(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
        self.clients.add(ws)
        try:
            async for raw in ws:
                d = json.loads(raw)["d"]
                kind, data = d["requestType"], d.get("requestData") or {}
                ok, resp, code = True, {}, 100
                if kind in ("StartStream", "StopStream", "ToggleStream"):
                    self.stream_requests.append(kind)
                if kind == "GetSourceScreenshot":
                    self.shots.append(data.get("sourceName"))
                    how = self.mevo[min(len(self.shots), len(self.mevo)) - 1]
                    if data.get("sourceName") != "Mevo SRT" or how == "missing":
                        ok, code = False, 600
                    elif how == "dead":
                        ok, code = False, 702
                    else:
                        resp = {"imageData": "data:image/png;base64,AAAA"}
                elif kind == "GetStreamStatus":
                    resp = {"outputActive": self.main_live}
                elif kind == "GetOutputList":
                    outs = [{"outputName": "adv_stream", "outputActive": self.main_live}]
                    outs += [{"outputName": "aitum_multi_output_" + n, "outputActive": True} for n in sorted(self.running)]
                    resp = {"outputs": outs}
                elif kind == "CallVendorRequest" and data.get("vendorName") == "aitum-multistream":
                    rt, rd = data["requestType"], data.get("requestData") or {}
                    if rt == "get_outputs":
                        inner = {"outputs": [{"name": n, "vertical": False} for n in self.aitum], "success": True}
                    elif rt in ("start_output", "stop_output"):
                        name = rd.get("output")
                        self.calls.append((rt, name))
                        (self.running.add if rt == "start_output" else self.running.discard)(name)
                        inner = {"success": True}
                    else:
                        inner = {"success": False}
                    resp = {"vendorName": "aitum-multistream", "requestType": rt, "responseData": inner}
                elif kind not in ("StartStream", "StopStream", "ToggleStream"):
                    ok, code = False, 204
                await ws.send(json.dumps({"op": 7, "d": {"requestType": kind, "requestId": d["requestId"],
                                                           "requestStatus": {"result": ok, "code": code},
                                                           "responseData": resp}}))
        finally:
            self.clients.discard(ws)

    async def emit_stream(self, started):
        self.main_live = started
        state = "OBS_WEBSOCKET_OUTPUT_STARTED" if started else "OBS_WEBSOCKET_OUTPUT_STOPPED"
        for ws in list(self.clients):
            await ws.send(json.dumps({"op": 5, "d": {"eventType": "StreamStateChanged", "eventIntent": 64,
                                                       "eventData": {"outputActive": started, "outputState": state}}}))


async def until(cond, timeout=3.0):
    end = asyncio.get_event_loop().time() + timeout
    while not cond():
        if asyncio.get_event_loop().time() > end:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.01)


async def run(fake, body, password=PASSWORD):
    async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"server_port": port, "server_password": password}, f)
        mod = load(f.name)
        mod.log = lambda *a: fake.logs.append(" ".join(map(str, a)))
        mod.notify = lambda *a: fake.notes.append(a)
        task = asyncio.create_task(mod.main())
        try:
            await body(fake)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            os.unlink(f.name)


async def test_go_live_starts_every_output():
    async def body(fake):
        await until(lambda: fake.clients)
        assert fake.subscriptions == 64, fake.subscriptions
        await fake.emit_stream(True)
        await until(lambda: len(fake.calls) == 2)
        assert fake.calls == [("start_output", "YouTube Output"), ("start_output", "Kick Output")], fake.calls
    await run(FakeObs(), body)


async def test_attaching_to_a_live_obs_starts_nothing():
    async def body(fake):
        await until(lambda: fake.clients)
        await asyncio.sleep(0.3)
        assert fake.calls == [], fake.calls
    await run(FakeObs(main_live=True), body)


async def test_an_output_already_running_is_left_alone():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        await until(lambda: len(fake.calls) == 1)
        await asyncio.sleep(0.2)
        assert fake.calls == [("start_output", "Kick Output")], fake.calls
    await run(FakeObs(running={"YouTube Output"}), body)


async def test_stopping_the_main_stream_stops_only_running_outputs():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(False)
        await until(lambda: len(fake.calls) == 1)
        await asyncio.sleep(0.2)
        assert fake.calls == [("stop_output", "YouTube Output")], fake.calls
    await run(FakeObs(running={"YouTube Output"}, main_live=True), body)


async def test_a_stream_stopped_during_the_delay_starts_nothing():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        fake.main_live = False  # stopped again before the delay ran out
        await asyncio.sleep(0.4)
        assert [c for c in fake.calls if c[0] == "start_output"] == [], fake.calls
    await run(FakeObs(), body)


async def test_a_wrong_password_never_gets_in_and_keeps_retrying():
    async def body(fake):
        await asyncio.sleep(0.4)
        assert fake.authed == 0 and fake.calls == []
    await run(FakeObs(), body, password="wrong")


async def test_it_reconnects_after_obs_restarts():
    async def body(fake):
        await until(lambda: fake.clients)
        for ws in list(fake.clients):
            await ws.close()
        await until(lambda: fake.authed >= 2)
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        await until(lambda: len(fake.calls) == 2)
    await run(FakeObs(), body)


async def test_go_live_with_a_working_mevo_stays_quiet():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        await until(lambda: fake.shots)
        await asyncio.sleep(0.2)
        assert fake.shots == ["Mevo SRT"], fake.shots
        assert fake.notes == [], fake.notes
        assert not [l for l in fake.logs if "WARNING" in l], fake.logs
    await run(FakeObs(), body)


async def test_go_live_with_a_dead_mevo_warns_loudly_and_leaves_the_stream_alone():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        await until(lambda: fake.notes)
        await asyncio.sleep(0.2)
        assert fake.shots == ["Mevo SRT"] * 3, fake.shots  # retried before warning
        assert len(fake.notes) == 1, fake.notes
        assert "camera" in fake.notes[0][0].lower(), fake.notes
        assert "power cycle" in fake.notes[0][1].lower(), fake.notes
        assert any("WARNING" in l and "702" in l for l in fake.logs), fake.logs
        assert fake.stream_requests == [], fake.stream_requests
        assert fake.main_live
        # the outputs still started: the warning doesn't hold up going live
        assert [c for c in fake.calls if c[0] == "start_output"] == [
            ("start_output", "YouTube Output"), ("start_output", "Kick Output")], fake.calls
    await run(FakeObs(mevo=("dead",)), body)


async def test_a_mevo_that_renders_on_a_retry_does_not_warn():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        await until(lambda: len(fake.shots) == 2)
        await asyncio.sleep(0.2)
        assert fake.shots == ["Mevo SRT"] * 2, fake.shots
        assert fake.notes == [], fake.notes
    await run(FakeObs(mevo=("dead", "ok")), body)


async def test_no_mevo_input_skips_the_check_without_warning():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        await until(lambda: fake.shots)
        await asyncio.sleep(0.2)
        assert fake.shots == ["Mevo SRT"], fake.shots  # a missing input isn't retried
        assert fake.notes == [], fake.notes
        assert any("no input named" in l for l in fake.logs), fake.logs
    await run(FakeObs(mevo=("missing",)), body)


async def test_attaching_to_a_live_obs_does_not_check_the_mevo():
    async def body(fake):
        await until(lambda: fake.clients)
        await asyncio.sleep(0.3)
        assert fake.shots == [] and fake.notes == [], (fake.shots, fake.notes)
    await run(FakeObs(main_live=True, mevo=("dead",)), body)


async def test_a_stream_stopped_during_the_delay_does_not_check_the_mevo():
    async def body(fake):
        await until(lambda: fake.clients)
        await fake.emit_stream(True)
        fake.main_live = False
        await asyncio.sleep(0.4)
        assert fake.shots == [] and fake.notes == [], (fake.shots, fake.notes)
    await run(FakeObs(mevo=("dead",)), body)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            asyncio.run(t())
            print("ok  ", t.__name__)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("FAIL", t.__name__, "::", type(e).__name__, e)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
