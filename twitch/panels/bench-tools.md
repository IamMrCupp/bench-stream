# Twitch panel: bench tools

The About-page panel that answers "what's running on screen?" Paste the four fields into a new panel on the channel's About page (Edit Panels → `+`).

| Field | Value |
|---|---|
| Panel title | `Bench tools` |
| Image | [`bench-tools.png`](bench-tools.png) — 320×100 PNG, rendered from [`bench-tools.svg`](bench-tools.svg) |
| Image links to | `https://github.com/IamMrCupp` |
| Description | The block below, as-is |

## Description

```markdown
What runs this stream and this bench. All open source.

**[benchhud](https://github.com/IamMrCupp/benchhud)** — the HUD. Scope and thermal camera in one picture, so the part that's cooking glows. Plus live meters and the job card.

**[multichat](https://github.com/IamMrCupp/megarohas_multichat)** — Twitch and YouTube chat in one overlay, a reply dock, and saved title, category and tag presets for both. My fork of [megarohas's](https://github.com/megarohas/megarohas_multichat) MIT project; duplexchat is its Go rewrite.

**[bench-stream](https://github.com/IamMrCupp/bench-stream)** — OBS helpers: scene switching, mic recovery, camera tuning.

**[bench-parts](https://github.com/IamMrCupp/bench-parts)** — parts inventory, used against a job.

**[benchhud-intake](https://github.com/IamMrCupp/benchhud-intake)** — job intake. Customer details live here, nowhere the stream can see.

**[bench-suite](https://github.com/IamMrCupp/bench-suite)** — the bench apps in one install, Ubuntu or Mac.
```

## Limits

From Twitch's help center, checked 2026-11-24:

- **Image:** [Channel Page Setup](https://help.twitch.tv/s/article/channel-page-setup) says no larger than 320 px wide and 300 px high, under 2.9 MB. The older [How to Edit Info Panels](https://help.twitch.tv/s/article/how-to-edit-info-panels) says 320 × 600 and under 1 MB. This image is 320 × 100 and about 10 KB, so it fits both.
- **Description:** Markdown, no HTML. Neither article states a character limit, so the panel editor's own counter is the check. The block above is under 1,000 characters, links included.

## What's in it, and what isn't

- **In:** the tools behind the stream and the bench, plus **bench-suite**, because the next question after "what's that?" is "can I run it?"
- **Chat:** the bench runs **megarohas_multichat** (`multichat.service`), a fork of megarohas's MIT-licensed project with a reply dock and a stream info panel (`/info`: title, category and tags for both platforms, with saved presets) added, so that's the one listed, with credit to the original. **duplexchat** is its Go rewrite and isn't in use yet, so it gets a mention, not a line of its own.
- **Out:** **homebrew-bench** — it's how bench-suite installs on a Mac, and bench-suite's README already links it. **bench-recon** — the pentest app bench-suite installs off by default; it's never on stream.

## Changing the image

Edit the SVG, then re-render on a Mac. The text is set in Avenir Next; elsewhere rsvg falls back to a wider font and the title can run into the border.

```sh
rsvg-convert -w 320 -h 100 bench-tools.svg -o bench-tools.png
```

The colours are the bench's own: navy and gold from the shop logo, and the HUD meter's voltage, current and power colours along the bottom.
