import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent
    / "skills"
    / "blog-narration"
    / "scripts"
    / "generate_audio.py"
)


@pytest.fixture
def narration_module():
    spec = importlib.util.spec_from_file_location("blog_narration_generate_audio", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_exception_output_redacts_all_credentials(
    narration_module,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    google_key = "google-secret-sentinel"
    gemini_key = "gemini-secret-sentinel"
    bearer_token = "bearer-secret-sentinel"
    query_key = "query-secret-sentinel"

    monkeypatch.setenv("GOOGLE_AI_API_KEY", google_key)
    monkeypatch.setenv("GEMINI_API_KEY", gemini_key)

    google_module = types.ModuleType("google")
    google_module.genai = types.SimpleNamespace(Client=lambda **_kwargs: object())
    monkeypatch.setitem(sys.modules, "google", google_module)

    def raise_reflected_credentials(*_args, **_kwargs):
        raise RuntimeError(
            f"GOOGLE_AI_API_KEY={google_key}; GEMINI_API_KEY={gemini_key}; "
            f"Authorization: Bearer {bearer_token}; "
            f"https://example.invalid/tts?model=test&key={query_key}&format=wav"
        )

    monkeypatch.setattr(
        narration_module,
        "generate_audio_chunks",
        raise_reflected_credentials,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_audio.py", "--text", "Narrate this", "--json"],
    )

    assert narration_module.main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["status"] == "error"
    assert "[REDACTED]" in payload["error"]
    for sentinel in (google_key, gemini_key, bearer_token, query_key):
        assert sentinel not in output
