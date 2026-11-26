"""Tests for mevo-relay. Run: python3 tests/test_mevo_relay.py [path/to/mevo-relay]

Needs ffmpeg and ffprobe. Feeds a made-up stream with video and audio through the
relay over local UDP (and over SRT where this ffmpeg has it, as on the bench) and
checks what comes out. No camera, no network beyond 127.0.0.1.
"""
import json, os, shutil, socket, subprocess, sys, time, unittest

PATH = sys.argv.pop(1) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "mevo-relay")
PATH = os.path.abspath(PATH)
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def has_srt():
    if not HAVE_FFMPEG:
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-protocols"], capture_output=True, text=True).stdout
    return "srt" in out.split()


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def source(url, seconds=20):
    """A test stream with both a video and an audio track, like the Mevo's.

    The video is MPEG-4 Part 2, which ffmpeg never picks by itself for MPEG-TS
    (it would pick mpeg2video), so finding it on the far side proves a copy.
    """
    return subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-re",
         "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=25:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-c:v", "mpeg4", "-g", "25", "-c:a", "mp2", "-f", "mpegts", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def relay(src, dst):
    env = dict(os.environ, MEVO_RELAY_SRC=src, MEVO_RELAY_DST=dst, MEVO_RELAY_LOGLEVEL="error")
    return subprocess.Popen([PATH], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe(url):
    out = subprocess.run(
        ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_entries", "stream=codec_type,codec_name",
         "-of", "json", url], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout or "{}").get("streams", [])


def stop(*procs):
    for p in procs:
        if p and p.poll() is None:
            p.kill()
        if p:
            p.wait()


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg and ffprobe")
class Relay(unittest.TestCase):
    def check_video_only(self, src_url, relay_src):
        out_port = free_udp_port()
        r = s = None
        try:
            r = relay(relay_src, f"udp://127.0.0.1:{out_port}?pkt_size=1316")
            s = source(src_url)
            streams = probe(f"udp://127.0.0.1:{out_port}?timeout=15000000")
        finally:
            stop(s, r)
        self.assertEqual([(x["codec_type"], x["codec_name"]) for x in streams], [("video", "mpeg4")])

    def test_udp_feed_comes_out_video_only(self):
        port = free_udp_port()
        self.check_video_only(f"udp://127.0.0.1:{port}?pkt_size=1316", f"udp://127.0.0.1:{port}?timeout=10000000")

    @unittest.skipUnless(has_srt(), "this ffmpeg has no SRT")
    def test_srt_feed_comes_out_video_only(self):
        # The Mevo listens and the relay calls it, the way OBS called it before.
        port = free_udp_port()
        s_url = f"srt://127.0.0.1:{port}?mode=listener"
        out_port = free_udp_port()
        r = s = None
        try:
            s = source(s_url)
            time.sleep(1)  # let the listener come up; an SRT caller retries for a few seconds anyway
            r = relay(f"srt://127.0.0.1:{port}?timeout=5000000", f"udp://127.0.0.1:{out_port}?pkt_size=1316")
            streams = probe(f"udp://127.0.0.1:{out_port}?timeout=15000000")
        finally:
            stop(s, r)
        self.assertEqual([(x["codec_type"], x["codec_name"]) for x in streams], [("video", "mpeg4")])

    def test_exits_when_nothing_arrives(self):
        # The unit restarts it on exit, so a dead feed must end the process, not hang it.
        port = free_udp_port()
        r = relay(f"udp://127.0.0.1:{port}?timeout=2000000", f"udp://127.0.0.1:{free_udp_port()}")
        try:
            rc = r.wait(timeout=20)
        except subprocess.TimeoutExpired:
            stop(r)
            self.fail("mevo-relay kept running with no input")
        self.assertNotEqual(rc, 0)


    def test_exits_when_the_feed_stops_midstream(self):
        # The real dropout: frames flow, then stop. ffmpeg ends with exit code 0 here,
        # which is why the unit uses Restart=always; only the exit itself is checked.
        port = free_udp_port()
        r = s = None
        try:
            r = relay(f"udp://127.0.0.1:{port}?timeout=2000000", f"udp://127.0.0.1:{free_udp_port()}")
            s = source(f"udp://127.0.0.1:{port}?pkt_size=1316", seconds=6)
            s.wait(timeout=20)
            r.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("mevo-relay kept running after the feed stopped")
        finally:
            stop(s, r)


class Script(unittest.TestCase):
    def test_defaults_point_at_the_bench(self):
        with open(PATH) as f:
            text = f.read()
        self.assertIn("srt://192.168.7.33:4201?timeout=5000000", text)
        self.assertIn("udp://127.0.0.1:4202?pkt_size=1316", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
