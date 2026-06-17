import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPipeline:
    """Test suite for main pipeline orchestrator."""

    def test_pipeline_run_function_exists(self):
        """Validate pipeline module exports run function."""
        from src.pipeline import run_automated_dubbing_pipeline
        import inspect

        sig = inspect.signature(run_automated_dubbing_pipeline)
        assert "video_url" in sig.parameters
        assert "output_dir" in sig.parameters
        assert "temp_dir" in sig.parameters

    def test_pipeline_parameters_have_defaults(self):
        """Ensure pipeline accepts reasonable defaults."""
        from src.pipeline import run_automated_dubbing_pipeline
        import inspect

        sig = inspect.signature(run_automated_dubbing_pipeline)
        assert sig.parameters["temp_dir"].default == "temp_assets"
        assert sig.parameters["output_dir"].default == "output"
        assert sig.parameters["whisper_model"].default == "base"

    def test_pipeline_module_imports_all_submodules(self):
        """Verify all pipeline dependencies are available."""
        from src import pipeline

        # Should have imports for all modules
        assert hasattr(pipeline, "download_video_and_audio")
        assert hasattr(pipeline, "transcribe_audio")
        assert hasattr(pipeline, "translate_to_khmer_script")
        assert hasattr(pipeline, "translate_segments_to_khmer_subtitles")
        assert hasattr(pipeline, "generate_dubbed_video")

    def test_pipeline_passes_translated_subtitle_segments_to_dubbing(self, monkeypatch, temp_dir):
        """Pipeline should pass translated subtitle segments into the dubbing step."""
        from src import pipeline

        monkeypatch.setattr(
            pipeline,
            "download_video_and_audio",
            lambda url, output_dir="temp_assets": {
                "video_path": str(temp_dir / "video.mp4"),
                "audio_path": str(temp_dir / "audio.wav"),
            },
        )
        monkeypatch.setattr(
            pipeline,
            "transcribe_audio",
            lambda audio_path, model_size="base": {
                "language": "en",
                "transcript": "Hello world",
                "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "Hello world"}],
            },
        )
        monkeypatch.setattr(
            pipeline,
            "translate_to_khmer_script",
            lambda transcript, source_lang="auto": {"khmer_script": "km script"},
        )
        monkeypatch.setattr(
            pipeline,
            "translate_segments_to_khmer_subtitles",
            lambda segments, source_lang="auto": {
                "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "km subtitle"}]
            },
        )

        captured = {}

        def fake_generate_dubbed_video(**kwargs):
            captured.update(kwargs)
            return {"output_video_path": "output.mp4"}

        monkeypatch.setattr(pipeline, "generate_dubbed_video", fake_generate_dubbed_video)

        result = pipeline.run_automated_dubbing_pipeline(
            "https://example.com/video",
            temp_dir=str(temp_dir / "temp"),
            output_dir=str(temp_dir / "output"),
        )

        assert captured["subtitle_segments"] == [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "km subtitle"}
        ]
        assert captured["burn_subtitles"] is True
        assert result["subtitle_translation"]["segments"] == [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "km subtitle"}
        ]
