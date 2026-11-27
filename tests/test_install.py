#!/usr/bin/env python3
"""Tests for install.sh's user part. Run: python3 tests/test_install.py

Runs install.sh against a throwaway HOME, with stand-ins for systemctl and
kbuildsycoca6 on PATH, so it never touches the real user's files or services.
"""
import os, shutil, stat, subprocess, sys, tempfile, unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INSTALL = os.path.join(ROOT, "install.sh")
DROPIN = "50-portal-no-rt.conf"


class UserInstall(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.bin = tempfile.mkdtemp()
        self.calls = os.path.join(self.bin, "calls")
        for tool in ("systemctl", "kbuildsycoca6", "kwriteconfig6", "qdbus6", "udevadm"):
            path = os.path.join(self.bin, tool)
            with open(path, "w") as f:
                f.write(f'#!/bin/sh\necho "{tool} $*" >> "{self.calls}"\n')
            os.chmod(path, 0o755)
        self.env = {**os.environ, "HOME": self.home, "PATH": self.bin + os.pathsep + os.environ["PATH"]}

    def tearDown(self):
        shutil.rmtree(self.home)
        shutil.rmtree(self.bin)

    def run_install(self, *args):
        return subprocess.run(["sh", INSTALL, *args], env=self.env, capture_output=True, text=True, check=True).stdout

    def test_portal_dropin_goes_where_pipewire_reads_client_config(self):
        self.run_install()
        dst = os.path.join(self.home, ".config", "pipewire", "client.conf.d", DROPIN)
        with open(dst) as got, open(os.path.join(ROOT, "pipewire", "client.conf.d", DROPIN)) as want:
            self.assertEqual(got.read(), want.read())
        self.assertEqual(stat.S_IMODE(os.stat(dst).st_mode), 0o644)

    def test_diff_lists_the_dropin_until_installed(self):
        dst = os.path.join(self.home, ".config", "pipewire", "client.conf.d", DROPIN)
        self.assertIn(f"not installed: {dst}", self.run_install("--diff"))
        self.run_install()
        self.assertNotIn(dst, self.run_install("--diff"))

    def test_install_never_starts_or_restarts_anything(self):
        self.run_install()
        with open(self.calls) as f:
            calls = [line for line in f.read().split("\n") if line]
        # The only systemd call is the reload; the KDE app list rebuild is the only other tool.
        self.assertEqual([c for c in calls if c.startswith("systemctl")], ["systemctl --user daemon-reload"])
        self.assertEqual([c for c in calls if not c.startswith(("systemctl", "kbuildsycoca6"))], [])


class PortalDropin(unittest.TestCase):
    def test_rule_matches_only_the_portal_and_turns_module_rt_off(self):
        with open(os.path.join(ROOT, "pipewire", "client.conf.d", DROPIN)) as f:
            rules = [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]
        text = " ".join(rules)
        self.assertTrue(text.startswith("context.properties.rules"), text)
        self.assertIn('matches = [ { application.process.binary = "xdg-desktop-portal" } ]', text)
        self.assertIn("update-props = { module.rt = false }", text)


if __name__ == "__main__":
    if os.geteuid() == 0:
        sys.exit("run as a normal user: install.sh refuses root for the user part")
    unittest.main()
