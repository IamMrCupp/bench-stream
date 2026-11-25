"""Tests for obs-micwatch's decision. Run: python3 tests/test_obs_micwatch.py [path/to/obs-micwatch]"""
import importlib.machinery, importlib.util, os, sys, tempfile, unittest

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
    def reason(self, usb):
        action, reason = mw.decide(DEV, {}, [], "DJI Mic", usb)
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

    def test_missing_root_is_unknown(self):
        self.assertIsNone(mw.usb_state(os.path.join(self.root, "nope"), "2ca3:4011"))


if __name__ == "__main__":
    unittest.main()
