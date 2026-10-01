#!/usr/bin/env python3
"""Validate against the installed Omarchy shell and Qt tooling."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
shell = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy')) / 'shell'
lint = shutil.which('qmllint') or '/usr/lib/qt6/bin/qmllint'
if not (shell / 'Ui/qmldir').is_file():
    raise SystemExit(f'Omarchy shell imports not found: {shell}')


def run(command):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run(command, cwd=root, check=True)


run(['omarchy', 'plugin', 'validate', str(root)])
# Quickshell maps the shell to qs.*. Standalone qmllint needs that mapping too.
# The temporary symlink is outside the plugin directory.
with tempfile.TemporaryDirectory(prefix='python-releases-qml-') as directory:
    (Path(directory) / 'qs').symlink_to(shell, target_is_directory=True)
    run([lint, '-I', str(shell), '-I', directory, 'BarWidget.qml', 'Panel.qml',
         'Action.qml', 'Label.qml', 'Selection.js', 'Translations.js'])
run(['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
run(['node', 'tests/test_selection.cjs'])
run(['node', 'tests/test_translations.cjs'])
