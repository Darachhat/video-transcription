import shutil
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Fixture providing a workspace-local temporary directory for test assets."""
    temp_root = Path(".test_tmp")
    temp_root.mkdir(exist_ok=True)

    test_dir = temp_root / uuid.uuid4().hex
    test_dir.mkdir(parents=True, exist_ok=True)

    try:
        yield test_dir
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


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
