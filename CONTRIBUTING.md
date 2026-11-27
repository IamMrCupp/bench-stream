# Contributing

Contributions are welcome — bug fixes, new helpers, docs.

bench-stream is open source under the [AGPL-3.0-or-later](LICENSE), and I sell
commercial licences to anyone the AGPL doesn't fit. That only works if the
rights over every line are clean, so two rules apply to every contribution.

## Sign off every commit (DCO)

Each commit must carry a [Developer Certificate of Origin](https://developercertificate.org/)
sign-off. It's your statement that you wrote the change, or otherwise have the
right to submit it. Add it with `-s`:

```sh
git commit -s -m "fix(setup): describe the change"
```

That appends `Signed-off-by: Your Name <you@example.com>`, matching your git
identity. A pull request with an unsigned commit won't be merged — fix it with
`git commit --amend -s` or `git rebase --signoff main` and force-push.

## Licensing of contributions

By contributing, you license your contribution under the project's current
license, the [GNU Affero General Public License v3.0 or later](LICENSE). You
also agree that it may be included in commercially licensed versions of
bench-stream, and that the maintainer may relicense it, along with the rest of the
project, under any license they choose, including another open-source license
such as MIT or GPL.

## Before you start

Open an issue before anything large — a new service, anything that changes what `install.sh` writes to a machine. Small fixes can go straight to a pull request.

Never put a real password, token or key in an issue, a pull request or a test, and never a camera frame from the bench. Use placeholders and made-up pictures, the way the tests already do.

Every helper that talks to OBS gets a test against the fake OBS in `tests/`. Run them before you push:

```sh
python3 tests/test_obs_golive.py
python3 tests/test_obs_micwatch.py
python3 tests/test_obs_sceneswitch.py
python3 tests/test_mevo_watch.py
python3 tests/test_install.py      # Linux
python3 tests/test_mevo_relay.py   # needs ffmpeg
```
