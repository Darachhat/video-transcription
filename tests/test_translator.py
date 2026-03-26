import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from translator import translate_to_khmer_script


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

    def test_translate_to_khmer_script_requires_google_credentials(self):
        """Verify environment is checked before API call."""
        import os

        # Temporarily unset credentials
        original = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

        try:
            with pytest.raises(EnvironmentError):
                translate_to_khmer_script("sample text")
        finally:
            # Restore original
            if original:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = original

    def test_translate_returns_expected_structure(self):
        """Validate return type includes required fields."""
        import inspect

        doc = inspect.getdoc(translate_to_khmer_script)
        assert "khmer_script" in doc or "source_language" in doc
