import pytest
from pathlib import Path


@pytest.fixture
def temp_dir(tmp_path):
    """Fixture providing a temporary directory for test assets."""
    return tmp_path


@pytest.fixture
def sample_audio_path(temp_dir):
    """Fixture for a dummy audio file path (not created, just path)."""
    return str(temp_dir / "sample.wav")


@pytest.fixture
def sample_video_path(temp_dir):
    """Fixture for a dummy video file path."""
    return str(temp_dir / "sample.mp4")


@pytest.fixture
def sample_transcript() -> str:
    """Fixture for a sample transcript text."""
    return (
        "Hello everyone, today we are going to explore the amazing world of artificial intelligence "
        "and how it is transforming our daily lives. Artificial intelligence is not just a buzzword anymore, "
        "it is real technology that is shaping our future."
    )
