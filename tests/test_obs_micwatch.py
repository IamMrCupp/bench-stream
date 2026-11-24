"""Tests for obs-micwatch's decision. Run: python3 tests/test_obs_micwatch.py [path/to/obs-micwatch]"""
import importlib.machinery, importlib.util, os, sys, unittest

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


if __name__ == "__main__":
    unittest.main()
