<!--
Title: Conventional Commits, under 70 chars. e.g. fix(micwatch): describe the change
-->

Closes #

## Summary

<!-- What changed and why. Name the tradeoff if there was one. -->

## Test plan

<!-- What you ran, on the bench or against the fake OBS, and what it printed. -->

- [ ] Tests pass (`python3 tests/test_*.py`)
- [ ] Checked on the bench, or says why not

## Stream-safety check

- [ ] No password, token or key, and nothing that prints one
- [ ] No camera frame or screenshot from the bench
- [ ] Nothing starts a stream or an output without someone pressing Start
