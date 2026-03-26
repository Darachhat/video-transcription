import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dubbing import synthesize_khmer_tts, replace_video_audio, cleanup_temp_files


class TestDubbing:
    """Test suite for TTS and video merging module."""

    def test_synthesize_khmer_tts_validates_input(self):
        """Ensure TTS module validates non-empty script."""
        with pytest.raises(ValueError):
            synthesize_khmer_tts("", "/tmp/output.wav")

        with pytest.raises(ValueError):
            synthesize_khmer_tts("   ", "/tmp/output.wav")

    def test_replace_video_audio_validates_file_paths(self, temp_dir):
        """Verify video and audio paths are validated."""
        nonexistent_video = str(temp_dir / "missing.mp4")
        nonexistent_audio = str(temp_dir / "missing.wav")
        output_path = str(temp_dir / "output.mp4")

        with pytest.raises(FileNotFoundError):
            replace_video_audio(nonexistent_video, nonexistent_audio, output_path)

    def test_cleanup_temp_files_handles_missing_files(self, temp_dir):
        """Ensure cleanup doesn't raise on missing files."""
        missing_paths = [str(temp_dir / "missing1.wav"), str(temp_dir / "missing2.wav")]

        # Should not raise
        cleanup_temp_files(missing_paths)

    def test_cleanup_temp_files_removes_existing_files(self, temp_dir):
        """Verify cleanup actually removes files."""
        test_file = temp_dir / "test.wav"
        test_file.write_text("dummy audio content")

        assert test_file.exists()
        cleanup_temp_files([str(test_file)])
        assert not test_file.exists()

    def test_cleanup_temp_files_handles_none_input(self):
        """Ensure cleanup handles None gracefully."""
        cleanup_temp_files(None)  # Should not raise

    def test_generate_dubbed_video_signature(self):
        """Validate generate_dubbed_video function signature."""
        from dubbing import generate_dubbed_video
        import inspect

        sig = inspect.signature(generate_dubbed_video)
        assert "original_video_path" in sig.parameters
        assert "khmer_script" in sig.parameters
        assert "output_dir" in sig.parameters
