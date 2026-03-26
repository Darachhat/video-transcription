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
        assert hasattr(pipeline, "generate_dubbed_video")
