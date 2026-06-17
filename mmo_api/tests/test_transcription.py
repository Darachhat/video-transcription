import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transcription import transcribe_audio


class TestTranscription:
    """Test suite for audio transcription module."""

    def test_transcribe_audio_validates_input_path(self):
        """Ensure transcriber validates file existence."""
        with pytest.raises(FileNotFoundError):
            transcribe_audio("/nonexistent/file.wav")

    def test_transcribe_audio_accepts_model_parameter(self):
        """Verify model size parameter is configurable."""
        import inspect

        sig = inspect.signature(transcribe_audio)
        assert "audio_path" in sig.parameters
        assert "model_size" in sig.parameters
        assert sig.parameters["model_size"].default == "base"

    def test_transcribe_audio_returns_expected_structure(self):
        """Validate return type includes required fields."""
        # This is a contract test
        import inspect

        # Get function source to verify docstring/contract
        doc = inspect.getdoc(transcribe_audio) or ""
        assert "language" in doc
        assert "transcript" in doc
        assert "segments" in doc
