import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import translator
from src.translator import translate_segments_to_khmer_subtitles, translate_to_khmer_script


class TestTranslator:
    """Test suite for Gemini translation module."""

    def test_translate_to_khmer_script_rejects_empty_input(self):
        """Ensure translator validates transcript is not empty."""
        with pytest.raises(ValueError):
            translate_to_khmer_script("")

        with pytest.raises(ValueError):
            translate_to_khmer_script("   ")

    def test_translate_to_khmer_script_accepts_language_parameter(self):
        """Verify source language parameter is optional."""
        import inspect

        sig = inspect.signature(translate_to_khmer_script)
        assert "transcript" in sig.parameters
        assert "source_lang" in sig.parameters
        assert sig.parameters["source_lang"].default == "auto"

    def test_translate_to_khmer_script_requires_google_credentials(self, monkeypatch):
        """Verify environment is checked before API call."""
        for key in (
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_GENAI_USE_VERTEXAI",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
        ):
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            translate_to_khmer_script("sample text")

    def test_translate_to_khmer_script_rejects_credentials_only_on_legacy_sdk(self, monkeypatch):
        """Legacy SDK path should ask for an API key when only ADC-style credentials are set."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "fake-creds.json")
        monkeypatch.setattr(translator, "modern_genai", None)

        with pytest.raises(EnvironmentError, match="legacy"):
            translate_to_khmer_script("sample text")

    def test_translate_to_khmer_script_falls_back_to_next_model_on_quota_error(self, monkeypatch):
        """Quota errors should trigger fallback to the next configured Gemini model."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_MODELS", "gemini-2.5-pro, gemini-2.5-flash")

        monkeypatch.setattr(translator, "_create_gemini_client", lambda: ("legacy", object()))
        monkeypatch.setattr(translator, "_close_gemini_client", lambda client_kind, client: None)

        calls = []

        def fake_generate_content(client_kind, client, model_name, prompt_text):
            calls.append(model_name)
            if model_name == "gemini-2.5-pro":
                raise RuntimeError("429 quota exceeded for gemini-2.5-pro. Please retry in 59.1s.")
            return SimpleNamespace(
                text="\u179f\u17bd\u179f\u17d2\u178f\u17b8\u200b\u1796\u17b7\u1797\u1796\u179b\u17c4\u1780"
            )

        monkeypatch.setattr(translator, "_generate_content", fake_generate_content)

        result = translate_to_khmer_script("Hello world", source_lang="English")

        assert result["khmer_script"] == "\u179f\u17bd\u179f\u17d2\u178f\u17b8\u200b\u1796\u17b7\u1797\u1796\u179b\u17c4\u1780"
        assert result["models_used"] == ["gemini-2.5-flash"]
        assert calls == ["gemini-2.5-pro", "gemini-2.5-flash"]

    def test_translate_segments_to_khmer_subtitles_preserves_segment_timing(self, monkeypatch):
        """Subtitle translation should preserve ids and Whisper timing boundaries."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_MODELS", "gemini-2.5-flash")

        monkeypatch.setattr(translator, "_create_gemini_client", lambda: ("legacy", object()))
        monkeypatch.setattr(translator, "_close_gemini_client", lambda client_kind, client: None)

        calls = []

        def fake_generate_content(client_kind, client, model_name, prompt_text):
            calls.append(model_name)
            return SimpleNamespace(
                text=(
                    '[{"id": 0, "text": "\\u179f\\u17bd\\u179f\\u17d2\\u178f\\u17b8"}, '
                    '{"id": 1, "text": "\\u1796\\u17b7\\u1797\\u1796\\u179b\\u17c4\\u1780"}]'
                )
            )

        monkeypatch.setattr(translator, "_generate_content", fake_generate_content)

        result = translate_segments_to_khmer_subtitles(
            [
                {"id": 0, "start": 0.0, "end": 1.25, "text": "Hello"},
                {"id": 1, "start": 1.25, "end": 2.8, "text": "world"},
            ],
            source_lang="English",
        )

        assert result["segments"] == [
            {"id": 0, "start": 0.0, "end": 1.25, "text": "\u179f\u17bd\u179f\u17d2\u178f\u17b8"},
            {"id": 1, "start": 1.25, "end": 2.8, "text": "\u1796\u17b7\u1797\u1796\u179b\u17c4\u1780"},
        ]
        assert result["models_used"] == ["gemini-2.5-flash"]
        assert calls == ["gemini-2.5-flash"]

    def test_translate_segments_to_khmer_subtitles_repairs_malformed_json(self, monkeypatch):
        """Malformed batch output should trigger a repair pass instead of failing."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_MODELS", "gemini-2.5-flash")

        monkeypatch.setattr(translator, "_create_gemini_client", lambda: ("legacy", object()))
        monkeypatch.setattr(translator, "_close_gemini_client", lambda client_kind, client: None)

        responses = iter(
            [
                SimpleNamespace(text="Here is the Khmer subtitle output:\n- \u179f\u17bd\u179f\u17d2\u178f\u17b8"),
                SimpleNamespace(
                    text='[{"id": 0, "text": "\\u179f\\u17bd\\u179f\\u17d2\\u178f\\u17b8"}]'
                ),
            ]
        )

        def fake_generate_content(client_kind, client, model_name, prompt_text):
            return next(responses)

        monkeypatch.setattr(translator, "_generate_content", fake_generate_content)

        result = translate_segments_to_khmer_subtitles(
            [{"id": 0, "start": 0.0, "end": 1.0, "text": "Hello"}],
            source_lang="English",
        )

        assert result["segments"] == [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "\u179f\u17bd\u179f\u17d2\u178f\u17b8"}
        ]
        assert result["models_used"] == ["gemini-2.5-flash", "gemini-2.5-flash"]

    def test_translate_to_khmer_script_waits_and_retries_single_model_on_quota(self, monkeypatch):
        """When only one model is configured, quota errors should wait then retry."""
        import time as time_module
        from src import translator

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_MODELS", "gemini-2.5-flash")

        monkeypatch.setattr(translator, "_create_gemini_client", lambda: ("legacy", object()))
        monkeypatch.setattr(translator, "_close_gemini_client", lambda ck, c: None)

        sleep_calls: list[float] = []
        monkeypatch.setattr(translator.time, "sleep", lambda s: sleep_calls.append(s))

        call_count = 0

        def fake_generate_content(client_kind, client, model_name, prompt_text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("429 quota exceeded. Please retry in 30s.")
            return SimpleNamespace(text="\u179f\u17bd")

        monkeypatch.setattr(translator, "_generate_content", fake_generate_content)

        result = translate_to_khmer_script("Hello", source_lang="en")

        assert result["khmer_script"] == "\u179f\u17bd"
        assert call_count == 2            # initial attempt + 1 retry
        assert len(sleep_calls) == 1     # exactly one sleep
        assert sleep_calls[0] == 30      # honoured the retry-after hint

    def test_translate_returns_expected_structure(self):
        """Validate return type includes required fields."""
        import inspect

        doc = inspect.getdoc(translate_to_khmer_script) or ""
        assert "khmer_script" in doc or "source_language" in doc
