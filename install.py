#!/usr/bin/env python3
"""Install the local plugin and enable it in the running Omarchy shell."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path(__file__).resolve().parent
config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy"
target = config / "plugins" / "frank.python-releases"
stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
shell = config / "shell.json"
already_enabled = False
if shell.exists():
    backup = shell.with_name("shell.json.bak.python-releases-" + stamp)
    shutil.copy2(shell, backup)
    print("Konfiguration gesichert:", backup, flush=True)
    data = json.loads(shell.read_text())
    changed = False
    for entries in data.get("bar", {}).get("layout", {}).values():
        for entry in entries:
            if entry.get("id") == "frank.python-releases":
                already_enabled = True
                if "language" in entry:
                    del entry["language"]
                    changed = True
    if changed:
        with tempfile.NamedTemporaryFile(mode="w", dir=config, delete=False) as stream:
            temp = Path(stream.name)
            try:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                temp.chmod(shell.stat().st_mode & 0o777)
                os.replace(temp, shell)
            finally:
                temp.unlink(missing_ok=True)
if target.exists():
    backup = config / "plugin-backups" / ("frank.python-releases-" + stamp)
    shutil.copytree(target, backup)
    print("Plugin gesichert:", backup, flush=True)
target.mkdir(parents=True, exist_ok=True)
for name in ("manifest.json", "BarWidget.qml", "Panel.qml", "Label.qml", "Action.qml", "Translations.js", "Selection.js", "releases.py", "README.md", "VALIDATION.md", "LICENSE"):
    shutil.copy2(source / name, target / name)
# Remove the previous entry point after the complete replacement has been copied.
(target / "Widget.qml").unlink(missing_ok=True)
subprocess.run(["omarchy", "plugin", "validate", str(target)], check=True)
subprocess.run(["omarchy-shell", "shell", "rescanPlugins"], check=True)
subprocess.run(["omarchy", "plugin", "enable", "frank.python-releases"] + ([] if already_enabled else ["--section", "right", "--index", "0"]), check=True)
print("Omarchy-Shell wird neu geladen …", flush=True)
subprocess.run(["omarchy", "restart", "shell"], check=True)
print("Installiert:", target)
