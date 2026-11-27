# Changelog

## [0.5.1](https://github.com/IamMrCupp/bench-stream/compare/v0.5.0...v0.5.1) (2026-11-27)


### Bug Fixes

* **mevo-relay:** restart after 2 s and test the whole gap OBS sees ([ea23de9](https://github.com/IamMrCupp/bench-stream/commit/ea23de99a1d552aec39ec5ec6d6f9f8ffb8de7e8))
* **mevo-relay:** restart on a flat 5 s delay so a long outage can't slow every reconnect ([d8fa790](https://github.com/IamMrCupp/bench-stream/commit/d8fa790fdc30628bbaf01527cd67c8f0ffbb11e3))

## [0.5.0](https://github.com/IamMrCupp/bench-stream/compare/v0.4.1...v0.5.0) (2026-11-27)


### Features

* **mevo-relay:** warn when the Mevo stops sending video ([551872e](https://github.com/IamMrCupp/bench-stream/commit/551872e37478b7aabbf21366b51917bf1fba8695))


### Bug Fixes

* **mevo-relay:** retry a warning that didn't show, skip it when the stream stops mid-check ([37cd7b4](https://github.com/IamMrCupp/bench-stream/commit/37cd7b445d861aba0af826bca9b1c9c024a289d5))

## [0.4.1](https://github.com/IamMrCupp/bench-stream/compare/v0.4.0...v0.4.1) (2026-11-26)


### Bug Fixes

* **udev:** remove the thermal no-storage rule, the experiment is over ([d406550](https://github.com/IamMrCupp/bench-stream/commit/d406550a107f00ffa09b02db160cc75ace986a5c))

## [0.4.0](https://github.com/IamMrCupp/bench-stream/compare/v0.3.2...v0.4.0) (2026-11-26)


### Features

* **mevo-relay:** strip the Mevo's audio before OBS sees it ([b66e5ef](https://github.com/IamMrCupp/bench-stream/commit/b66e5efc225f7602c200cb00637e98eac5b53fee))


### Bug Fixes

* **mevo-relay:** start in about 3 s, back off while the Mevo is off, test copy and mid-stream stalls ([f9f1e74](https://github.com/IamMrCupp/bench-stream/commit/f9f1e74f7ff6042c8905b274e85012e2590f0a6c))

## [0.3.2](https://github.com/IamMrCupp/bench-stream/compare/v0.3.1...v0.3.2) (2026-11-25)


### Documentation

* **twitch:** mention multichat's stream info presets in the bench tools panel ([bf20b61](https://github.com/IamMrCupp/bench-stream/commit/bf20b61b69b1c89eaa35a4eddc47aed68bcc4b30))

## [0.3.1](https://github.com/IamMrCupp/bench-stream/compare/v0.3.0...v0.3.1) (2026-11-25)


### Documentation

* **twitch:** add the bench tools About panel ([9c4c60d](https://github.com/IamMrCupp/bench-stream/commit/9c4c60d361192949a7f0099b7c9353ea944e0346))
* **twitch:** list the multichat fork the bench runs, credit upstream ([5ce10ab](https://github.com/IamMrCupp/bench-stream/commit/5ce10ab2fc51f3e6101f7d0947ee8a13b0890f92))
* **twitch:** match the panel tagline to what's listed, note the render font ([c2a0616](https://github.com/IamMrCupp/bench-stream/commit/c2a06160d53f6d03738a0fd5f4ab2efa751a6aa1))

## [0.3.0](https://github.com/IamMrCupp/bench-stream/compare/v0.2.1...v0.3.0) (2026-11-25)


### Features

* **micwatch:** log when the linked mic sends pure silence ([a467698](https://github.com/IamMrCupp/bench-stream/commit/a467698ebad3a7ba5e26c6c7984cb85a5ed2a5cc))


### Bug Fixes

* **micwatch:** reset the silence run on errors, log unreadable samples, test the wiring ([b0fc320](https://github.com/IamMrCupp/bench-stream/commit/b0fc3207d981a4888bbe5e3f6d9df1be2f64760c))

## [0.2.1](https://github.com/IamMrCupp/bench-stream/compare/v0.2.0...v0.2.1) (2026-11-25)


### Bug Fixes

* **micwatch:** name a serial mismatch, don't say replug while the receiver enumerates ([8117016](https://github.com/IamMrCupp/bench-stream/commit/811701647d170c5bc23a4d8ec1ed5f5318cbdf77))
* **micwatch:** say when the DJI receiver comes back on USB with no audio ([0601c0f](https://github.com/IamMrCupp/bench-stream/commit/0601c0fe6fa03e97a8c12353060f0f746d57ff98))

## [0.2.0](https://github.com/IamMrCupp/bench-stream/compare/v0.1.0...v0.2.0) (2026-11-25)


### Features

* **sceneswitch:** follow window focus and add Meta+number scene shortcuts ([88f77d6](https://github.com/IamMrCupp/bench-stream/commit/88f77d674c8c0a7532e2970bc5315d188c273e48))


### Bug Fixes

* **sceneswitch:** keep the arm's position across reconnects, bound focus switches, no launch feedback ([b56938e](https://github.com/IamMrCupp/bench-stream/commit/b56938ef490c6c1f3a51d6691382fe9a59cef05e))

## 0.1.0 (2026-11-24)


### Features

* import the bench's stream helpers, units and udev rules ([840643f](https://github.com/IamMrCupp/bench-stream/commit/840643fdc919415de91d639bb9b5ba3d47248720))


### Bug Fixes

* **install:** stop on the first failed copy, refuse a directory in the way, flag lost exec bits ([8854002](https://github.com/IamMrCupp/bench-stream/commit/8854002bdc8d16b6fe6527f847558006531f8032))
