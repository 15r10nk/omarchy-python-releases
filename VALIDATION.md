# Review fixes — 1.5.1

- Unexpectedly empty established schedules retain cached events and emit warnings.
- Staleness is calculated locally with a 19-hour threshold, allowing the six-hour
  feed schedule, twelve-hour client cache and one hour of scheduling tolerance.
- 31 Python tests, both JavaScript suites and QML/plugin validation passed.

# Feed migration validation

Version **1.5.0**, checked on **2026-10-01**.

- Plugin validator and QML/JavaScript lint passed.
- 28 Python tests passed, including feed validation, oversized/invalid responses,
  offline cache preservation, source warnings, first deployment, partial source
  failures and complete outages.
- Both JavaScript suites passed, including all 13 locales.
- Live collection produced a validated feed from the official Python sources.
- Repository is public and GitHub Pages deployment succeeded in
  [workflow run 36912154742](https://github.com/15r10nk/omarchy-python-releases/actions/runs/36912154742).
- The live feed validated with 25 series and no source warnings.
- Version 1.5.0 was installed with configuration/plugin backups; the shell restarted
  successfully and the plugin is enabled. Its installed helper fetched the hosted
  JSON into the local cache without errors.

## Previous desktop validation

Version **1.4.0**, checked on **2026-09-29** with Omarchy **4.0.3-1** and
Quickshell **0.3.1**.

## Automated checks

Run `python3 scripts/validate.py` from the source checkout.

- Omarchy plugin manifest validation: passed.
- QML/JavaScript lint: passed using the installed shell imports. See README for
  the temporary import mapping and two targeted tooling annotations.
- Python regression tests: 20 passed.
- JavaScript selection and translation suites: passed, including all 13 locales.

## Desktop checks

- Shell summon: opened the overview; rendering inspected in a screenshot.
- Shell hide and Escape: closed the overview.
- Down and Enter: selected a series and persisted its favorite setting.
  Toggling again cleared it.
- Disable/re-enable: native plugin manager reported the expected states.
- Shell restart: plugin loaded without observed plugin runtime errors.
- Native Git installation: installed and enabled from a temporary local Git
  repository through `omarchy plugin add`.
- Native removal: removed both the development installation and test Git clone.
  The development installation was then restored.
- Original bar position and settings: restored and compared with the saved
  configuration after the lifecycle checks.

Pointer clicks and Tab/Shift+Tab switching between panels still need an
interactive check. Synthetic pointer input did not provide a reliable test.
The native Git test used a local repository; remote hosting and marketplace
submission have not been tested or performed.

## Before publication

- Click the bar to open/close, click outside to dismiss, and check right/middle
  click refresh.
- Check Tab/Shift+Tab switching with another panel available.
- Repeat validation on the final publication checkout.
