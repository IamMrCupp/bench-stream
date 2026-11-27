"""Tests for mevo-watch. Run: python3 tests/test_mevo_watch.py [path/to/mevo-watch]

The decision is tested directly. The end-to-end tests run the script with a fake
`systemctl` that reports a made-up relay state and a fake `notify-send` that
writes down what it was asked to show, so no real unit or desktop is touched.
"""
import importlib.machinery, importlib.util, os, subprocess, sys, tempfile, time, unittest

PATH = sys.argv.pop(1) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "mevo-watch")
PATH = os.path.abspath(PATH)
loader = importlib.machinery.SourceFileLoader("mevo_watch", PATH)
spec = importlib.util.spec_from_loader("mevo_watch", loader)
mw = importlib.util.module_from_spec(spec)
loader.exec_module(mw)

S = 1_000_000  # µs per second, systemd's monotonic unit


def unit(active="active", sub="running", pid=1234, started=0):
    return {"ActiveState": active, "SubState": sub, "ExecMainPID": str(pid),
            "ExecMainStartTimestampMonotonic": str(started)}


class Classify(unittest.TestCase):
    def test_a_long_run_has_video(self):
        self.assertEqual(mw.classify(unit(started=100 * S), 200 * S, stable=15), "up")

    def test_a_run_shorter_than_stable_is_not_yet_up(self):
        self.assertEqual(mw.classify(unit(started=100 * S), 110 * S, stable=15), "down")

    def test_the_restart_backoff_is_down(self):
        # what the bench shows between failed connections to the Mevo
        st = unit(active="activating", sub="auto-restart", pid=0, started=50 * S)
        self.assertEqual(mw.classify(st, 500 * S, stable=15), "down")

    def test_a_stopped_or_failed_relay_is_off(self):
        self.assertEqual(mw.classify(unit(active="inactive", sub="dead", pid=0), 500 * S), "off")
        self.assertEqual(mw.classify(unit(active="failed", sub="failed", pid=0), 500 * S), "off")

    def test_no_main_process_is_not_up(self):
        self.assertEqual(mw.classify(unit(pid=0, started=1 * S), 500 * S), "down")
        self.assertEqual(mw.classify(unit(started=0), 500 * S), "down")

    def test_garbage_is_not_up(self):
        self.assertEqual(mw.classify(unit(pid="x"), 500 * S), "down")


class Outage(unittest.TestCase):
    def test_one_warning_after_down_after_then_back(self):
        w = mw.Watch(down_after=60)
        self.assertIsNone(w.tick("up", 0))
        events = [w.tick("down", t) for t in range(5, 300, 5)]
        warns = [e for e in events if e]
        self.assertEqual(warns, [("warn", 60)])  # first not-up reading at 5, warning at 65
        self.assertEqual(w.tick("up", 400), ("back", 395))
        self.assertIsNone(w.tick("up", 405))

    def test_a_short_blip_never_warns_and_logs_nothing(self):
        w = mw.Watch(down_after=60)
        for t in range(0, 50, 5):
            self.assertIsNone(w.tick("down", t))
        self.assertIsNone(w.tick("up", 50))

    def test_a_second_outage_warns_again(self):
        w = mw.Watch(down_after=10)
        self.assertEqual(w.tick("down", 0), None)
        self.assertEqual(w.tick("down", 10), ("warn", 10))
        self.assertEqual(w.tick("up", 20)[0], "back")
        self.assertEqual(w.tick("down", 30), None)
        self.assertEqual(w.tick("down", 40), ("warn", 10))

    def test_stopping_the_relay_resets_without_a_warning(self):
        w = mw.Watch(down_after=10)
        w.tick("down", 0)
        self.assertEqual(w.tick("off", 5), ("off", 0))
        self.assertIsNone(w.tick("off", 50))  # said once
        self.assertIsNone(w.tick("down", 60))  # the outage clock starts over
        self.assertEqual(w.tick("down", 70), ("warn", 10))

    def test_message_rounds_to_minutes(self):
        self.assertEqual(mw.minutes(62), "1 min")
        self.assertEqual(mw.minutes(30), "30 s")


FAKE_SYSTEMCTL = """#!/bin/sh
echo "$*" >> "$FAKE_DIR/systemctl.args"
cat "$FAKE_DIR/state"
"""
FAKE_NOTIFY = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_DIR/notes"
echo 42
"""


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = self.dir.name
        for name, body in (("systemctl", FAKE_SYSTEMCTL), ("notify-send", FAKE_NOTIFY)):
            with open(os.path.join(d, name), "w") as f:
                f.write(body)
            os.chmod(os.path.join(d, name), 0o755)
        self.proc = None

    def tearDown(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        if self.proc:
            self.proc.communicate()
        self.dir.cleanup()

    def set_state(self, st):
        tmp = os.path.join(self.dir.name, "state.tmp")
        with open(tmp, "w") as f:
            f.write("".join(f"{k}={v}\n" for k, v in st.items()))
        os.replace(tmp, os.path.join(self.dir.name, "state"))

    def notes(self):
        try:
            with open(os.path.join(self.dir.name, "notes")) as f:
                return f.read().splitlines()
        except FileNotFoundError:
            return []

    def start(self):
        env = dict(os.environ, FAKE_DIR=self.dir.name, PATH=self.dir.name + os.pathsep + os.environ["PATH"],
                   MEVO_WATCH_INTERVAL="0.05", MEVO_WATCH_STABLE="0.3", MEVO_WATCH_DOWN_AFTER="0.6",
                   PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen([sys.executable, PATH], env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True)

    def wait_for(self, cond, timeout=5):
        end = time.monotonic() + timeout
        while not cond():
            if time.monotonic() > end:
                self.fail("timed out waiting")
            time.sleep(0.02)

    def now_us(self):
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 1000

    def test_a_dead_mevo_gets_one_critical_notification_then_a_back_one(self):
        self.set_state(unit(active="activating", sub="auto-restart", pid=0, started=1))
        self.start()
        self.wait_for(lambda: self.notes())
        time.sleep(0.5)  # still down: no second warning
        notes = self.notes()
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("-u critical", notes[0])
        self.assertIn("Overhead camera is down", notes[0])
        self.assertIn("power cycle", notes[0])

        # the camera is power cycled: a run starts and lasts past STABLE
        self.set_state(unit(started=self.now_us()))
        self.wait_for(lambda: len(self.notes()) == 2)
        back = self.notes()[1]
        self.assertIn("Overhead camera is back", back)
        self.assertIn("-r 42", back)  # replaces the warning
        self.assertIn("-u normal", back)

        self.proc.terminate()
        out, _ = self.proc.communicate(timeout=5)
        self.assertIn("needs a power cycle", out)
        self.assertIn("feed is back", out)
        with open(os.path.join(self.dir.name, "systemctl.args")) as f:
            self.assertIn("--user show mevo-relay", f.readline())

    def test_a_healthy_relay_stays_quiet(self):
        self.set_state(unit(started=self.now_us() - 3600 * S))
        self.start()
        time.sleep(1.2)
        self.assertEqual(self.notes(), [])

    def test_a_stopped_relay_never_warns(self):
        self.set_state(unit(active="inactive", sub="dead", pid=0))
        self.start()
        time.sleep(1.2)
        self.assertEqual(self.notes(), [])


class Unit(unittest.TestCase):
    def test_unit_runs_the_installed_script(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "systemd", "user", "mevo-watch.service")
        with open(path) as f:
            text = f.read()
        self.assertIn("ExecStart=%h/.local/bin/mevo-watch", text)
        self.assertIn("Restart=always", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
