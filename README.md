# Python Releases for Omarchy

A Python release countdown for the Omarchy Quattro bar. Click to explore release
schedules, prereleases, support status and end-of-life dates. Star a version
series to follow its next release in the bar.

## Requirements

- Omarchy with the Quattro/Quickshell shell and native `omarchy plugin` commands.
  Tested on **Omarchy 4.0.3-1** and **Quickshell 0.3.1** with the installed Qt 6
  components. Older Waybar-based installations are not supported.
- Python **3.10 or later**, standard library only; no pip packages.
- Internet access for updates. Cached data remains available offline.
- An Omarchy theme font with the Python Nerd Font glyph.

## Install

Once a public repository is available, use Omarchy's native plugin manager.
**Replace the placeholder URL** with the actual repository URL:

```sh
omarchy plugin add https://github.com/OWNER/REPOSITORY.git --enable
```

The ID `frank.python-releases` is a namespace, not a required local username.
The plugin installs under `~/.config/omarchy/plugins/frank.python-releases/`
and defaults to the right bar section.

For an unpublished local source checkout:

```sh
python3 install.py
```

This optional development helper backs up the plugin and `shell.json`, preserves
position and settings, copies and validates the files, enables the widget, and
restarts the shell. It is not needed for native Git installation. A failed restart
returns an error; Omarchy refuses to restart an active lock screen, so retry after
unlocking. Avoid copying development files over a Git-managed installation you
intend to update with `omarchy plugin update`, as this creates local Git changes.

## Use

- Click the bar widget to open or close the overview.
- Select a series to view its support status, EOL and releases.
- Click **☆** to follow a series in the bar; click **★** again for automatic
  selection. This persists across restarts and monitors. Browsing other series
  does not change the favorite. The star appears in the overview, not in the bar.
- **Upcoming dates** lists future milestones across all series.
- Click an event to open its official release page or release PEP.
- Right-/middle-click the bar, click **Refresh**, or press **R / Ctrl+R** in the
  panel to refresh. Successful requests within ten seconds are coalesced.
- **Up/Down** selects a series; **Enter/Space** toggles its star.
- **Tab/Shift+Tab** switches between Omarchy bar panels.
- **Escape** or clicking outside closes the panel.

Example bar label: ` 3.15.0 · 5 d`. An asterisk marks stale/incomplete data or a
fetch error, with an explanation in the panel. A selected series without a known
future release remains visible with `—` instead of a countdown.

## Configure

```sh
omarchy bar move frank.python-releases --section right
omarchy bar set frank.python-releases countdown all
```

Settings live inline in the widget's `shell.json` layout entry:

```json
{"id": "frank.python-releases", "countdown": "feature", "favorite": ""}
```

- `feature` (default): next stable feature release, such as 3.15.0.
- `stable`: next stable release, including patches.
- `all`: also includes alpha, beta and release candidates.
- `favorite`: empty for automatic selection, or a series such as `3.14`, set by
  the stars. A favorite follows that series' next stable release including
  patches; `all` also includes prereleases.

On a scheduled release day the countdown says “today”. Releases confirmed by the
archive are excluded from the countdown.

## Language

The widget always uses the shell's system locale, with no language selector.
Supported: German, English, French, Spanish, Italian, Portuguese, Dutch, Polish,
Russian, Turkish, Simplified Chinese, Japanese and Korean. Other languages fall
back to English. Regional variants share translations; dates and times use the
system locale's regional format. Month-only EOL dates stay month-only.
Legacy `language` settings are ignored. After changing system language, restart
the shell with the new locale; logging out and back in may be necessary.

## Data, refresh and permissions

Sources: [Python Developer's Guide](https://devguide.python.org/versions/), linked
[release PEPs](https://peps.python.org/), and the
[Python release archive](https://www.python.org/downloads/).

All sources refresh every **12 hours**, regardless of the selected series. The
countdown is recalculated every minute from the cache using the local date.
Failed updates retry after ten minutes. Successful sources update independently;
only unavailable data is retained from the cache. The panel flags incomplete
results. The update timestamp reflects the last successful partial fetch; a full
outage retains the previous timestamp. Invalid caches are discarded and rebuilt.

Future dates are provisional. Security updates often have no fixed schedule.
A past PEP date alone is not proof of publication. Historical prereleases are
included where their dated entries can be parsed; unknown EOL dates are shown
as unspecified. The PEP takes precedence for the countdown if source dates differ.

The QML plugin runs in the existing shell with your user permissions. It starts
a Python helper for HTTPS requests and JSON processing. The helper writes only
under `$XDG_CACHE_HOME/omarchy-python-releases/` (normally `~/.cache/…`), with
network timeouts and an atomic cache shared across monitors. Preferences are
saved through Omarchy's scoped settings API. Browser links open when clicked.

No administrator privileges, background service, remote build, downloaded code
or second Quickshell process are required. Python itself is never installed or
updated. The optional local installer writes user configuration and backups as
described above.

## Update, disable and remove

For a Git-managed installation:

```sh
omarchy plugin update frank.python-releases
```

If an update leaves old QML loaded, run `omarchy restart shell` after unlocking.

```sh
omarchy plugin disable frank.python-releases
omarchy plugin enable frank.python-releases
omarchy plugin remove frank.python-releases
```

Removal uses Omarchy's confirmation/backup behavior. The cache is retained;
you can delete `~/.cache/omarchy-python-releases/` separately if desired.

## Development and validation

`BarWidget.qml` owns the bar button, loads `Panel.qml` and forwards its lifecycle.
The panel uses Omarchy's `Panel`, `KeyboardPanel` and `PanelKeyCatcher` components.
`Selection.js` handles favorites; `Translations.js` contains translations;
`releases.py` retrieves and caches data. The structure follows the
[Omarchy development guide](https://plugins.omarchy.org/develop.html).

Tests additionally need Node.js; QML checks need Qt's `qmllint` and the installed
Omarchy shell imports:

```sh
python3 scripts/validate.py
```

This runs `omarchy plugin validate`, `qmllint`, Python regression tests and
JavaScript tests. The script provides standalone `qmllint` with a temporary `qs`
namespace mapping **outside** the plugin directory. Two narrowly scoped lint
annotations handle Quickshell 0.3.1's missing `QProcess::ExitStatus` tooling type;
other warnings are not disabled.

Desktop checks cover Escape, summon/hide, disable/re-enable, restart, removal
and Git installation. Pointer clicks and panel switching still need interactive
verification. See [VALIDATION.md](VALIDATION.md) for results.

```sh
omarchy-shell shell summon frank.python-releases '{}'
omarchy-shell shell hide frank.python-releases
omarchy plugin list --json
```

Replace the repository URL placeholder before submitting a marketplace listing.
These tools do not publish or submit the plugin.

## License

[MIT](LICENSE) · Copyright (c) 2026 Frank.
