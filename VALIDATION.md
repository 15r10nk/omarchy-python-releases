# Validation

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
- Replace the README repository URL placeholder with the public repository URL.
- Repeat validation on the final publication checkout.
