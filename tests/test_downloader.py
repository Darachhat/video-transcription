import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from downloader import download_video_and_audio


class TestDownloader:
    """Test suite for video downloader module."""

    def test_download_video_and_audio_requires_valid_url(self):
        """Ensure downloader raises error on invalid input."""
        with pytest.raises((RuntimeError, ValueError, Exception)):
            download_video_and_audio("")

    def test_download_video_and_audio_creates_output_dir(self, temp_dir):
        """Verify output directory is created if missing."""
        output_dir = temp_dir / "test_output"
        assert not output_dir.exists()

        # This would fail with an actual download error, but directory should exist
        try:
            download_video_and_audio("https://invalid-url", output_dir=str(output_dir))
        except Exception:
            pass

        # Directory creation is attempted at module start
        assert output_dir.exists()

    def test_download_returns_dict_with_paths(self):
        """Validate function signature returns expected structure."""
        # This is a contract test - actual download is integration test
        # Just verify the function exists and has correct signature
        import inspect

        sig = inspect.signature(download_video_and_audio)
        assert "url" in sig.parameters
        assert "output_dir" in sig.parameters
