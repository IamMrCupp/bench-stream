"""Tests for obs-micwatch's decision. Run: python3 tests/test_obs_micwatch.py [path/to/obs-micwatch]"""
import asyncio, importlib.machinery, importlib.util, os, subprocess, sys, tempfile, unittest

PATH = sys.argv.pop(1) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "obs-micwatch")
loader = importlib.machinery.SourceFileLoader("micwatch", PATH)
spec = importlib.util.spec_from_loader("micwatch", loader)
mw = importlib.util.module_from_spec(spec)
loader.exec_module(mw)

DEV = "alsa_input.usb-DJI-01.analog-stereo"
NO_SOURCE = 4294967295


class Decide(unittest.TestCase):
    def test_linked_stream_is_left_alone(self):
        self.assertEqual(mw.decide(DEV, {DEV: 1716}, [(1716, "DJI Mic")], "DJI Mic")[0], "ok")

    def test_stream_on_no_source_after_reenumeration_reconnects(self):
        action, reason = mw.decide(DEV, {DEV: 1716}, [(NO_SOURCE, "DJI Mic")], "DJI Mic")
        self.assertEqual(action, "reconnect")
        self.assertIn("1716", reason)

    def test_stream_on_old_source_index_reconnects(self):
        self.assertEqual(mw.decide(DEV, {DEV: 1800}, [(1716, "DJI Mic")], "DJI Mic")[0], "reconnect")

    def test_device_absent_does_nothing(self):
        # transmitters off: the receiver has no audio interface, nothing to link to
        self.assertEqual(mw.decide(DEV, {}, [(NO_SOURCE, "DJI Mic")], "DJI Mic")[0], "ok")

    def test_missing_stream_reconnects(self):
        self.assertEqual(mw.decide(DEV, {DEV: 5}, [(84, "Desktop Audio")], "DJI Mic")[0], "reconnect")

    def test_other_inputs_are_ignored(self):
        outs = [(84, "Desktop Audio"), (NO_SOURCE, "Desktop Audio 2"), (5, "DJI Mic")]
        self.assertEqual(mw.decide(DEV, {DEV: 5}, outs, "DJI Mic")[0], "ok")

    def test_default_and_placeholder_devices_are_not_touched(self):
        for dev in ("default", mw.PLACEHOLDER, None, ""):
            self.assertEqual(mw.decide(dev, {"default": 1}, [], "DJI Mic")[0], "ok")


class Absent(unittest.TestCase):
    def reason(self, usb, dev="alsa_input.usb-DJI_Wireless_Mic_Rx_XSP12345678B-01.analog-stereo"):
        action, reason = mw.decide(dev, {}, [], "DJI Mic", usb)
        self.assertEqual(action, "ok")  # nothing to link to in any of these
        return reason

    def test_no_audio_mode_says_replug(self):
        r = self.reason([("0123456789AB", False)])
        self.assertIn("no audio interface", r)
        self.assertIn("0123456789AB", r)
        self.assertIn("replug", r)

    def test_receiver_off_usb(self):
        self.assertIn("isn't on USB", self.reason([]))

    def test_audio_mode_waits_for_pipewire(self):
        self.assertIn("waiting for PipeWire", self.reason([("XSP12345678B", True)]))

    def test_audio_under_another_serial_says_obs_points_elsewhere(self):
        r = self.reason([("NEWSERIAL", True)])
        self.assertIn("NEWSERIAL", r)
        self.assertIn("different device", r)

    def test_still_enumerating_is_not_a_replug(self):
        r = self.reason([("0123456789AB", None)])
        self.assertNotIn("replug", r)
        self.assertIn("coming up", r)

    def test_replug_only_when_every_match_lacks_audio(self):
        self.assertIn("waiting for PipeWire", self.reason([("0123456789AB", False), ("XSP12345678B", True)]))

    def test_unknown_usb_state(self):
        self.assertEqual(self.reason(None), "device absent")

    def test_usb_state_is_ignored_while_the_source_exists(self):
        self.assertEqual(mw.decide(DEV, {DEV: 5}, [(5, "DJI Mic")], "DJI Mic", [("x", False)])[0], "ok")


class UsbState(unittest.TestCase):
    """usb_state() against a made-up /sys/bus/usb/devices tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def device(self, name, vid, pid, serial, classes):
        os.makedirs(os.path.join(self.root, name))
        for f, v in (("idVendor", vid), ("idProduct", pid), ("serial", serial)):
            if v is None:
                continue
            with open(os.path.join(self.root, name, f), "w") as fh:
                fh.write(v + "\n")
        for n, cls in classes.items():
            iface = os.path.join(self.root, name, f"{name}:1.{n}")
            os.makedirs(iface)
            with open(os.path.join(iface, "bInterfaceClass"), "w") as fh:
                fh.write(cls + "\n")
            # sysfs also lists each interface at the top level, as a symlink
            os.symlink(iface, os.path.join(self.root, f"{name}:1.{n}"))

    def test_audio_mode(self):
        self.device("1-3", "2ca3", "4011", "XSP12345678B", {0: "03", 1: "01", 3: "01", 6: "ff"})
        self.assertEqual(mw.usb_state(self.root, "2ca3:4011"), [("XSP12345678B", True)])

    def test_no_audio_mode(self):
        self.device("1-3", "2ca3", "4011", "0123456789AB", {6: "ff"})
        self.assertEqual(mw.usb_state(self.root, "2ca3:4011"), [("0123456789AB", False)])

    def test_other_devices_are_ignored(self):
        self.device("1-4", "0fd9", "00a1", "CAM", {0: "01"})
        self.assertEqual(mw.usb_state(self.root, "2ca3:4011"), [])

    def test_no_interfaces_yet_is_unknown_audio(self):
        self.device("1-3", "2ca3", "4011", "0123456789AB", {})
        self.assertEqual(mw.usb_state(self.root, "2ca3:4011"), [("0123456789AB", None)])

    def test_missing_serial_reads_empty(self):
        self.device("1-3", "2ca3", "4011", None, {6: "ff"})
        self.assertEqual(mw.usb_state(self.root, "2ca3:4011"), [("", False)])
        self.assertIn("serial ?", mw.absent_reason([("", False)]))

    def test_undecodable_serial_does_not_raise(self):
        self.device("1-3", "2ca3", "4011", "x", {6: "ff"})
        with open(os.path.join(self.root, "1-3", "serial"), "wb") as fh:
            fh.write(b"\xff\xfe\n")
        self.assertEqual(len(mw.usb_state(self.root, "2ca3:4011")), 1)

    def test_hubs_and_other_devices_alongside(self):
        self.device("usb1", "1d6b", "0002", "0000:05:00.3", {0: "09"})
        self.device("1-3", "2ca3", "4011", "XSP12345678B", {0: "03", 1: "01"})
        self.device("1-3.2", "0fd9", "00a1", "CAM", {0: "01"})
        self.assertEqual(mw.usb_state(self.root, "2ca3:4011"), [("XSP12345678B", True)])

    def test_missing_root_is_unknown(self):
        self.assertIsNone(mw.usb_state(os.path.join(self.root, "nope"), "2ca3:4011"))


class SilenceRun(unittest.TestCase):
    def test_warns_once_after_the_limit_then_says_when_signal_is_back(self):
        s = mw.Silence(15)
        self.assertIsNone(s.update(True, 100))
        self.assertIsNone(s.update(True, 110))
        warn = s.update(True, 115)
        self.assertIn("pure silence for at least 15s", warn)
        self.assertIsNone(s.update(True, 120))  # once per run
        self.assertEqual(s.update(False, 125), "signal back on the mic")
        self.assertIsNone(s.update(False, 130))

    def test_signal_before_the_limit_starts_over(self):
        s = mw.Silence(15)
        s.update(True, 100)
        self.assertIsNone(s.update(False, 110))  # never warned, so nothing to say
        self.assertIsNone(s.update(True, 112))
        self.assertIsNone(s.update(True, 120))  # 8 s into the new run
        self.assertIsNotNone(s.update(True, 127))

    def test_a_failed_read_breaks_the_run(self):
        s = mw.Silence(15)
        s.update(True, 100)
        self.assertIsNone(s.update(None, 200))
        self.assertIsNone(s.update(True, 201))  # a new run starts here, not at 100
        self.assertIsNotNone(s.update(True, 216))

    def test_repeated_failed_reads_are_logged_once_and_recovery_too(self):
        s = mw.Silence(15)
        self.assertIsNone(s.update(None, 0))
        self.assertIsNone(s.update(None, 5))
        self.assertIn("can't read", s.update(None, 10))
        self.assertIsNone(s.update(None, 15))
        self.assertIn("again", s.update(False, 20))
        self.assertIsNone(s.update(False, 25))

    def test_reset_forgets_the_run_quietly(self):
        s = mw.Silence(15)
        s.update(True, 100)
        s.update(True, 120)
        s.reset()
        self.assertIsNone(s.update(False, 121))  # no "signal back" after a relink
        self.assertIsNone(s.update(True, 130))
        self.assertIsNone(s.update(True, 140))


class SilenceTick(unittest.TestCase):
    """The per-poll wiring run() uses, with a fake sampler instead of parec."""

    ZERO, NOISE = b"\x00" * 8, b"\x00\x00\xe4\x00" * 2

    def setUp(self):
        self.reads = []

    def reader(self, data):
        def read(device):
            self.reads.append(device)
            return data
        return read

    def tick(self, s, reason, now, data):
        return asyncio.run(s.tick(reason, "dji", now, self.reader(data)))

    def test_samples_only_while_linked_and_only_every_few_seconds(self):
        s = mw.Silence(15, every=5)
        self.tick(s, "linked", 0, self.ZERO)
        self.tick(s, "linked", 2, self.ZERO)   # too soon
        self.tick(s, "linked", 5, self.ZERO)
        self.tick(s, "device absent", 7, self.ZERO)
        self.assertEqual(self.reads, ["dji", "dji"])

    def test_silence_while_linked_warns(self):
        s = mw.Silence(15, every=5)
        msgs = [self.tick(s, "linked", t, self.ZERO) for t in (0, 5, 10, 15)]
        self.assertEqual(msgs[:3], [None, None, None])
        self.assertIn("pure silence", msgs[3])

    def test_leaving_linked_resets_the_run(self):
        s = mw.Silence(15, every=5)
        for t in (0, 5, 10):
            self.tick(s, "linked", t, self.ZERO)
        self.tick(s, "stream on source 1, device is source 2", 12, self.ZERO)
        self.assertIsNone(self.tick(s, "linked", 15, self.ZERO))  # a fresh run, not 15 s old

    def test_noise_never_warns(self):
        s = mw.Silence(15, every=5)
        self.assertEqual([self.tick(s, "linked", t, self.NOISE) for t in range(0, 60, 5)], [None] * 12)

    def test_zero_limit_never_samples(self):
        s = mw.Silence(0, every=5)
        for t in range(0, 60, 5):
            self.assertIsNone(self.tick(s, "linked", t, self.ZERO))
        self.assertEqual(self.reads, [])


class Sample(unittest.TestCase):
    """Pins the two parec settings the bench taught us."""

    def test_parec_call(self):
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["env"] = argv, kw.get("env", {})
            return subprocess.CompletedProcess(argv, 0, stdout=b"\x00\x00", stderr=b"")

        real = mw.subprocess.run
        mw.subprocess.run = fake_run
        try:
            self.assertEqual(mw.sample("dji"), b"\x00\x00")
        finally:
            mw.subprocess.run = real
        self.assertIn("--latency-msec=50", seen["argv"])  # else a 1 s run reads nothing
        self.assertEqual(seen["argv"][seen["argv"].index("parec") + 1:][:2], ["-d", "dji"])
        self.assertIn("node.dont-fallback=true", seen["env"]["PULSE_PROP"])  # else it records another mic
        self.assertEqual(seen["argv"][:3], ["timeout", "-k", "1"])

    def test_parec_missing_reads_nothing(self):
        def boom(argv, **kw):
            raise FileNotFoundError("timeout")

        real = mw.subprocess.run
        mw.subprocess.run = boom
        try:
            self.assertEqual(mw.sample("dji"), b"")
        finally:
            mw.subprocess.run = real


class IsSilent(unittest.TestCase):
    def s16(self, *xs):
        import struct
        return struct.pack(f"<{len(xs)}h", *xs)

    def test_all_zero_is_silent(self):
        self.assertTrue(mw.is_silent(self.s16(0, 0, 0, 0)))

    def test_a_quiet_noise_floor_is_not_silent(self):
        # 228, the bench's room noise with nobody talking; one non-zero sample is enough
        self.assertFalse(mw.is_silent(self.s16(0, 228, 0, 0)))
        self.assertFalse(mw.is_silent(self.s16(0, 0, -1, 0)))

    def test_nothing_read_is_no_answer(self):
        self.assertIsNone(mw.is_silent(b""))
        self.assertIsNone(mw.is_silent(b"\x00"))  # less than one sample

    def test_a_trailing_partial_sample_is_ignored(self):
        self.assertTrue(mw.is_silent(self.s16(0, 0) + b"\x01"))


if __name__ == "__main__":
    unittest.main()
