#!/usr/bin/env bash
# Create or update the Ctrl+Alt+E GNOME shortcut for correcteur-ia.
set -euo pipefail

NAME="Correcteur IA"
BINDING="<Control><Alt>e"
COMMAND="${1:-$(command -v correcteur-ia || true)}"

if [[ -z "$COMMAND" ]]; then
    echo "error: correcteur-ia is not installed or not in PATH" >&2
    echo "install it first (for example: pipx install .), then run this script" >&2
    exit 1
fi

if ! command -v gsettings >/dev/null 2>&1; then
    echo "error: this installer supports GNOME only" >&2
    echo "set a custom shortcut manually to: $COMMAND" >&2
    exit 1
fi

python3 - "$COMMAND" "$NAME" "$BINDING" <<'PY'
import ast
import subprocess
import sys

command, name, binding = sys.argv[1:4]
schema = "org.gnome.settings-daemon.plugins.media-keys"
custom = schema + ".custom-keybinding"
base = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"


def get(key, at=None):
    target = f"{custom}:{at}" if at else schema
    return subprocess.check_output(["gsettings", "get", target, key], text=True).strip()


def set_value(key, value, at=None):
    target = f"{custom}:{at}" if at else schema
    subprocess.check_call(["gsettings", "set", target, key, value])


raw = get("custom-keybindings")
if raw.startswith("@as "):
    raw = raw[4:]
paths = ast.literal_eval(raw) if raw else []

target = None
for path in paths:
    if get("name", path).strip("'\"") == name:
        target = path
        break

if target is None:
    index = 0
    existing = set(paths)
    while f"{base}/custom{index}/" in existing:
        index += 1
    target = f"{base}/custom{index}/"
    paths.append(target)
    set_value("custom-keybindings", str(paths))

set_value("name", name, target)
set_value("command", command, target)
set_value("binding", binding, target)
print(f"bound {binding} to {command} ({target})")
PY
