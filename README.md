# Correcteur IA

[![tests](https://github.com/khalil-lab/correcteur-ia/actions/workflows/tests.yml/badge.svg)](https://github.com/khalil-lab/correcteur-ia/actions/workflows/tests.yml)

Correct the text you have selected in any Wayland application with a global
shortcut, using a local Ollama model. No cloud API, no account, no data leaving
your machine.

**Shortcut:** select text, press `Ctrl+Alt+E`, and the corrected text replaces it
in place.

## Demo

```text
Selected:   je sui fatigue et je peu pas continuer
Corrected:  Je suis fatigué et je ne peux pas continuer.
```

A desktop notification confirms the result (`Texte corrigé.`) or explains why
nothing was replaced.

## How it works

```text
Ctrl+Alt+E
    |
    v
ydotool key ctrl+c  ->  wl-paste  ->  Ollama /api/generate
                                            |
                                            v
active window  <-  ydotool key ctrl+v  <-  wl-copy
```

1. The shortcut runs `correcteur-ia`.
2. The current selection is copied with `ydotool` and read with `wl-paste`.
3. The text is sent to a local Ollama endpoint with a prompt that preserves the
   original meaning, tone, formality, and language.
4. The corrected text is copied with `wl-copy` and pasted with `ydotool`.
5. `notify-send` reports success or failure.

## Requirements

- Linux with Wayland (tested on GNOME)
- [Ollama](https://ollama.com/download) running locally, with a model pulled
  (default: `llama3`)
- `ydotool` and a running `ydotoold`
- `wl-clipboard` (`wl-copy`, `wl-paste`)
- `libnotify` (`notify-send`)
- Python 3.9+

On Debian/Ubuntu:

```bash
sudo apt install ydotool wl-clipboard libnotify-bin
ollama pull llama3
```

`ydotool` needs access to `/dev/uinput` and the `ydotoold` daemon. Make sure your
user can use it before relying on the shortcut.

## Installation

```bash
git clone https://github.com/khalil-lab/correcteur-ia.git
cd correcteur-ia
pipx install .
```

With a virtual environment instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## Set up the shortcut

### GNOME

The included script creates or updates the GNOME custom shortcut
`Ctrl+Alt+E` and points it at the installed command:

```bash
./scripts/install-shortcut.sh
```

Verify it:

```bash
gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings
```

You can also set it manually in **Settings > Keyboard > Keyboard Shortcuts >
Custom Shortcuts**:

| Field | Value |
| --- | --- |
| Name | `Correcteur IA` |
| Command | `correcteur-ia` |
| Shortcut | `Ctrl+Alt+E` |

### KDE Plasma and other desktops

Create a custom shortcut in your desktop's keyboard settings with the command
`correcteur-ia` and the binding `Ctrl+Alt+E`.

## Usage

1. Select text in any application.
2. Press `Ctrl+Alt+E`.
3. Wait for the notification; the selection is replaced in place.

The command can also be run manually:

```bash
correcteur-ia
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORRECTEUR_IA_MODEL` | `llama3:latest` | Ollama model used for corrections |
| `CORRECTEUR_IA_URL` | `http://localhost:11434/api/generate` | Ollama generate endpoint |
| `CORRECTEUR_IA_TIMEOUT` | `180` | Request timeout in seconds |
| `CORRECTEUR_IA_KEEP_ALIVE` | `24h` | How long Ollama keeps the model loaded |

Example:

```bash
export CORRECTEUR_IA_MODEL="qwen2.5:7b"
```

When launched from a desktop shortcut, environment variables must be visible to
the session (for example, set them in `~/.profile` and log in again).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `Aucun texte sélectionné` | Select text before pressing the shortcut; confirm `wl-paste` returns the selection |
| `Erreur : ... ydotool` | Ensure `ydotoold` is running and `/dev/uinput` is accessible |
| Nothing is pasted | Confirm the target application accepts synthetic `Ctrl+V` |
| `Aucune correction reçue` | Check `ollama list` and that the configured model is pulled |
| Slow first correction | The model is loading; `keep_alive` keeps it warm for later runs |

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Tests mock the desktop tools and Ollama, so they run on any Linux CI machine.

## Privacy

Text is sent only to the Ollama endpoint configured in `CORRECTEUR_IA_URL`,
which defaults to localhost. Nothing is sent to a third-party service.

## License

MIT. See [LICENSE](LICENSE).
