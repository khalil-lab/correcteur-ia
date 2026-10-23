#!/usr/bin/env python3
"""Correct the selected text in any Wayland application with a local LLM."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

__version__ = "0.1.0"

DEFAULT_MODEL = "llama3:latest"
DEFAULT_URL = "http://localhost:11434/api/generate"
DEFAULT_TIMEOUT = 180.0
DEFAULT_KEEP_ALIVE = "24h"

COPY_DELAY = 0.4
PASTE_DELAY = 0.2

PROMPT_TEMPLATE = """You are a context-aware text correction assistant.

Rewrite the input into correct, natural language while preserving the user's
intended meaning, tone, level of formality, and language.

Fix spelling mistakes, typos, grammar, punctuation, missing words, incorrect
word forms, and malformed or incomplete sentences. Infer the most likely
intended wording when the input contains obvious mistakes, even if several
words need to be corrected. For example, "i stupiiid" should become
"I'm stupid."

Do not add new ideas or unnecessary details. Do not explain your corrections or
include notes, labels, or quotation marks. Return only the corrected text.
Always answer in the same language as the input. If the input is already
correct, return it unchanged.

Input:
{text}
"""


def get_model() -> str:
    """Return the Ollama model, honouring CORRECTEUR_IA_MODEL."""
    return os.environ.get("CORRECTEUR_IA_MODEL", DEFAULT_MODEL)


def get_url() -> str:
    """Return the Ollama generate endpoint, honouring CORRECTEUR_IA_URL."""
    return os.environ.get("CORRECTEUR_IA_URL", DEFAULT_URL)


def get_timeout() -> float:
    """Return the request timeout in seconds, honouring CORRECTEUR_IA_TIMEOUT."""
    raw = os.environ.get("CORRECTEUR_IA_TIMEOUT", str(DEFAULT_TIMEOUT))
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT


def get_keep_alive() -> str:
    """Return how long Ollama keeps the model loaded."""
    return os.environ.get("CORRECTEUR_IA_KEEP_ALIVE", DEFAULT_KEEP_ALIVE)


def notify(message: str) -> None:
    """Show a desktop notification, falling back to stderr."""
    try:
        subprocess.run(
            ["notify-send", "Correcteur IA", message],
            check=False,
        )
    except OSError:
        print(f"Correcteur IA: {message}", file=sys.stderr)


def build_prompt(text: str) -> str:
    """Build the instruction sent to the local model."""
    return PROMPT_TEMPLATE.format(text=text)


def request_correction(
    text: str,
    model: str | None = None,
    url: str | None = None,
    timeout: float | None = None,
) -> str:
    """Send text to Ollama and return the corrected text."""
    payload = json.dumps(
        {
            "model": model or get_model(),
            "prompt": build_prompt(text),
            "stream": False,
            "keep_alive": get_keep_alive(),
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url or get_url(),
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=timeout or get_timeout()) as response:
        data = json.load(response)

    return data.get("response", "").strip()


def copy_selection() -> None:
    """Copy the current selection to the clipboard."""
    subprocess.run(["ydotool", "key", "ctrl+c"], check=True)
    time.sleep(COPY_DELAY)


def read_clipboard() -> str:
    """Read the clipboard as text without adding a trailing newline."""
    result = subprocess.run(
        ["wl-paste", "--no-newline"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def paste_text(text: str) -> None:
    """Put text on the clipboard and paste it into the active window."""
    subprocess.run(["wl-copy"], input=text, text=True, check=True)
    time.sleep(PASTE_DELAY)
    subprocess.run(["ydotool", "key", "ctrl+v"], check=True)


def correct_selection() -> int:
    """Correct the current selection in place and return an exit status."""
    copy_selection()
    original = read_clipboard()

    if not original.strip():
        notify("Aucun texte sélectionné. Rien n'a été remplacé.")
        return 1

    corrected = request_correction(original)
    if not corrected:
        notify("Aucune correction reçue. Rien n'a été remplacé.")
        return 1

    paste_text(corrected)
    notify("Texte corrigé.")
    return 0


def print_usage() -> None:
    """Print command-line usage."""
    print("Usage: correcteur-ia")
    print()
    print("Correct the text currently selected in the active window.")
    print("Bind this command to a global shortcut (default: Ctrl+Alt+E).")
    print()
    print("Options:")
    print("  -h, --help     Show this help message")
    print("  -V, --version  Show the version")


def main(argv: list[str] | None = None) -> int:
    """Run the correction pipeline and report unexpected failures."""
    arguments = sys.argv[1:] if argv is None else argv

    if arguments in (["-h"], ["--help"], ["help"]):
        print_usage()
        return 0

    if arguments in (["-V"], ["--version"]):
        print(f"correcteur-ia {__version__}")
        return 0

    try:
        return correct_selection()
    except Exception as exc:  # noqa: BLE001 - surface the error to the user
        notify(f"Erreur : {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
