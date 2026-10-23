import json
from types import SimpleNamespace

import correcteur_ia


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_build_prompt_contains_input_and_language_rule():
    prompt = correcteur_ia.build_prompt("je sui fatigue")

    assert "je sui fatigue" in prompt
    assert "same language as the input" in prompt
    assert "Return only the corrected text" in prompt


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("CORRECTEUR_IA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("CORRECTEUR_IA_URL", "http://127.0.0.1:9999/api/generate")
    monkeypatch.setenv("CORRECTEUR_IA_TIMEOUT", "42")
    monkeypatch.setenv("CORRECTEUR_IA_KEEP_ALIVE", "1h")

    assert correcteur_ia.get_model() == "qwen2.5:7b"
    assert correcteur_ia.get_url() == "http://127.0.0.1:9999/api/generate"
    assert correcteur_ia.get_timeout() == 42.0
    assert correcteur_ia.get_keep_alive() == "1h"


def test_invalid_timeout_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("CORRECTEUR_IA_TIMEOUT", "not-a-number")

    assert correcteur_ia.get_timeout() == correcteur_ia.DEFAULT_TIMEOUT


def test_request_correction_sends_expected_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        captured["content_type"] = request.get_header("Content-type")
        return FakeResponse(json.dumps({"response": "  Bonjour.  "}).encode())

    monkeypatch.setattr(correcteur_ia.urllib.request, "urlopen", fake_urlopen)

    result = correcteur_ia.request_correction(
        "bonjour",
        model="llama3:latest",
        url="http://localhost:11434/api/generate",
        timeout=5,
    )

    assert result == "Bonjour."
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["timeout"] == 5
    assert captured["payload"]["model"] == "llama3:latest"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["keep_alive"] == "24h"
    assert "bonjour" in captured["payload"]["prompt"]
    assert captured["content_type"] == "application/json"


def test_request_correction_returns_empty_string_without_response(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(b"{}")

    monkeypatch.setattr(correcteur_ia.urllib.request, "urlopen", fake_urlopen)

    assert correcteur_ia.request_correction("bonjour") == ""


def test_copy_selection_presses_ctrl_c_and_waits(monkeypatch):
    calls = []
    monkeypatch.setattr(
        correcteur_ia.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )
    monkeypatch.setattr(
        correcteur_ia.time, "sleep", lambda seconds: calls.append(("sleep", seconds))
    )

    correcteur_ia.copy_selection()

    assert calls[0] == (["ydotool", "key", "ctrl+c"], {"check": True})
    assert calls[1] == ("sleep", correcteur_ia.COPY_DELAY)


def test_read_clipboard_returns_text(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == ["wl-paste", "--no-newline"]
        assert kwargs == {"capture_output": True, "text": True, "check": True}
        return SimpleNamespace(stdout="texte sélectionné")

    monkeypatch.setattr(correcteur_ia.subprocess, "run", fake_run)

    assert correcteur_ia.read_clipboard() == "texte sélectionné"


def test_paste_text_copies_waits_and_pastes(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(correcteur_ia.subprocess, "run", fake_run)
    monkeypatch.setattr(
        correcteur_ia.time, "sleep", lambda seconds: calls.append(("sleep", seconds))
    )

    correcteur_ia.paste_text("texte corrigé")

    assert calls[0] == (
        ["wl-copy"],
        {"input": "texte corrigé", "text": True, "check": True},
    )
    assert calls[1] == ("sleep", correcteur_ia.PASTE_DELAY)
    assert calls[2] == (["ydotool", "key", "ctrl+v"], {"check": True})


def test_notify_falls_back_to_stderr(monkeypatch, capsys):
    def failing_run(command, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(correcteur_ia.subprocess, "run", failing_run)

    correcteur_ia.notify("hello")

    assert "Correcteur IA: hello" in capsys.readouterr().err


def test_correct_selection_replaces_text(monkeypatch):
    calls = []

    monkeypatch.setattr(correcteur_ia, "copy_selection", lambda: calls.append("copy"))
    monkeypatch.setattr(correcteur_ia, "read_clipboard", lambda: "  bonjor  ")
    monkeypatch.setattr(
        correcteur_ia,
        "request_correction",
        lambda text: calls.append(("correct", text)) or "Bonjour.",
    )
    monkeypatch.setattr(
        correcteur_ia, "paste_text", lambda text: calls.append(("paste", text))
    )
    monkeypatch.setattr(correcteur_ia, "notify", lambda message: calls.append(("notify", message)))

    assert correcteur_ia.correct_selection() == 0
    assert calls == [
        "copy",
        ("correct", "  bonjor  "),
        ("paste", "Bonjour."),
        ("notify", "Texte corrigé."),
    ]


def test_correct_selection_handles_empty_selection(monkeypatch):
    calls = []

    monkeypatch.setattr(correcteur_ia, "copy_selection", lambda: None)
    monkeypatch.setattr(correcteur_ia, "read_clipboard", lambda: "   \n")
    monkeypatch.setattr(
        correcteur_ia,
        "request_correction",
        lambda text: calls.append("request") or "unused",
    )
    monkeypatch.setattr(correcteur_ia, "paste_text", lambda text: calls.append("paste"))
    monkeypatch.setattr(correcteur_ia, "notify", lambda message: calls.append(message))

    assert correcteur_ia.correct_selection() == 1
    assert "request" not in calls
    assert "paste" not in calls
    assert any("Aucun texte sélectionné" in str(item) for item in calls)


def test_correct_selection_handles_empty_correction(monkeypatch):
    calls = []

    monkeypatch.setattr(correcteur_ia, "copy_selection", lambda: None)
    monkeypatch.setattr(correcteur_ia, "read_clipboard", lambda: "bonjour")
    monkeypatch.setattr(correcteur_ia, "request_correction", lambda text: "")
    monkeypatch.setattr(correcteur_ia, "paste_text", lambda text: calls.append("paste"))
    monkeypatch.setattr(correcteur_ia, "notify", lambda message: calls.append(message))

    assert correcteur_ia.correct_selection() == 1
    assert "paste" not in calls
    assert any("Aucune correction reçue" in str(item) for item in calls)


def test_main_prints_help(capsys):
    assert correcteur_ia.main(["--help"]) == 0
    assert "Usage: correcteur-ia" in capsys.readouterr().out


def test_main_prints_version(capsys):
    assert correcteur_ia.main(["--version"]) == 0
    assert correcteur_ia.__version__ in capsys.readouterr().out


def test_main_reports_unexpected_error(monkeypatch):
    messages = []

    def failing_correct_selection():
        raise RuntimeError("ollama is down")

    monkeypatch.setattr(correcteur_ia, "correct_selection", failing_correct_selection)
    monkeypatch.setattr(correcteur_ia, "notify", messages.append)

    assert correcteur_ia.main() == 1
    assert messages == ["Erreur : ollama is down"]
