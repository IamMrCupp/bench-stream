# Changelog

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
