import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import dubbing
from src.dubbing import (
    cleanup_temp_files,
    create_khmer_subtitle_file,
    generate_dubbed_video,
    replace_video_audio,
    synthesize_khmer_tts,
)
from src.dubbing import (
    VOXCPM_AVAILABLE,
    DEFAULT_VOXCPM_MODEL,
    DEFAULT_VOXCPM_CFG_VALUE,
    DEFAULT_VOXCPM_INFERENCE_TIMESTEPS,
    DEFAULT_VOXCPM_DEVICE,
    DEFAULT_VOXCPM_LOAD_DENOISER,
    _resolve_tts_setting,
    _resolve_float_setting,
    _resolve_int_setting,
    _resolve_bool_setting,
    _format_srt_timestamp,
    _load_voxcpm_model,
)


def make_fake_voxcpm_helpers():
    """Create fresh captured dict and fake helper functions for VoxCPM2 monkeypatching."""
    captured = {}

    def fake_save_voxcpm_audio(
        khmer_script: str,
        output_wav_path,
        model_name: str,
        device: str,
        cfg_value: float,
        inference_timesteps: int,
        load_denoiser: bool = True,
    ) -> None:
        """Write a sentinel file so size checks pass."""
        captured["khmer_script"] = khmer_script
        captured["model_name"] = model_name
        captured["cfg_value"] = cfg_value
        captured["inference_timesteps"] = inference_timesteps
        captured["load_denoiser"] = load_denoiser
        Path(output_wav_path).write_bytes(b"fake-48k-wav")

    def fake_convert_audio_to_wav(
        input_audio_path,
        output_wav_path,
        ffmpeg_path: str,
    ) -> None:
        """Write a sentinel 44.1kHz WAV so existence checks pass."""
        captured["input_audio_path"] = str(input_audio_path)
        captured["output_wav_path"] = str(output_wav_path)
        Path(output_wav_path).write_bytes(b"fake-44k-wav")

    return captured, fake_save_voxcpm_audio, fake_convert_audio_to_wav


class TestDubbing:
    """Test suite for TTS, subtitles, and video merging."""

    def test_synthesize_khmer_tts_validates_input(self):
        """Ensure TTS module validates non-empty script."""
        with pytest.raises(ValueError):
            synthesize_khmer_tts("", "/tmp/output.wav")

        with pytest.raises(ValueError):
            synthesize_khmer_tts("   ", "/tmp/output.wav")

    def test_create_khmer_subtitle_file_writes_utf8_srt(self, temp_dir):
        """Subtitle helper should write valid SRT timing lines and Khmer text."""
        output_path = temp_dir / "khmer.srt"

        result = create_khmer_subtitle_file(
            [
                {"id": 0, "start": 0.0, "end": 1.25, "text": "\u179f\u17bd\u179f\u17d2\u178f\u17b8"},
                {"id": 1, "start": 1.25, "end": 2.5, "text": "\u1796\u17b7\u1797\u1796\u179b\u17c4\u1780"},
            ],
            str(output_path),
        )

        content = output_path.read_text(encoding="utf-8")
        assert result == str(output_path)
        assert "00:00:00,000 --> 00:00:01,250" in content
        assert "\u179f\u17bd\u179f\u17d2\u178f\u17b8" in content
        assert "\u1796\u17b7\u1797\u1796\u179b\u17c4\u1780" in content

    def test_replace_video_audio_validates_file_paths(self, temp_dir):
        """Verify video, audio, and subtitle paths are validated."""
        nonexistent_video = str(temp_dir / "missing.mp4")
        nonexistent_audio = str(temp_dir / "missing.wav")
        output_path = str(temp_dir / "output.mp4")

        with pytest.raises(FileNotFoundError):
            replace_video_audio(nonexistent_video, nonexistent_audio, output_path)

    def test_replace_video_audio_uses_subtitles_filter_when_requested(self, temp_dir, monkeypatch):
        """Burned subtitles should force a video re-encode with the subtitles filter."""
        video_path = temp_dir / "source.mp4"
        audio_path = temp_dir / "dubbed.wav"
        subtitle_path = temp_dir / "khmer.srt"
        output_path = temp_dir / "output.mp4"

        video_path.write_bytes(b"video")
        audio_path.write_bytes(b"audio")
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")

        commands = []

        def fake_run(command, capture_output, text):
            commands.append(command)
            if command[0] == "ffprobe":
                if str(video_path) in command:
                    return subprocess.CompletedProcess(command, 0, "4.0\n", "")
                return subprocess.CompletedProcess(command, 0, "2.0\n", "")

            output_path.write_bytes(b"merged-video")
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(dubbing.subprocess, "run", fake_run)

        result = replace_video_audio(
            str(video_path),
            str(audio_path),
            str(output_path),
            subtitle_file_path=str(subtitle_path),
        )

        ffmpeg_command = commands[-1]
        assert result == str(output_path)
        assert output_path.exists()
        assert "-vf" in ffmpeg_command
        assert any("subtitles=" in part for part in ffmpeg_command)
        assert "libx264" in ffmpeg_command

    def test_cleanup_temp_files_handles_missing_files(self, temp_dir):
        """Ensure cleanup doesn't raise on missing files."""
        missing_paths = [str(temp_dir / "missing1.wav"), str(temp_dir / "missing2.wav")]
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
        cleanup_temp_files(None)

    def test_generate_dubbed_video_creates_and_cleans_temp_subtitle_file(self, temp_dir, monkeypatch):
        """Full dubbing helper should create a subtitle file and clean temp assets by default."""
        original_video_path = temp_dir / "source.mp4"
        original_video_path.write_bytes(b"video")

        captured = {}

        def fake_synthesize_khmer_tts(khmer_script, output_wav_path, **kwargs):
            Path(output_wav_path).write_bytes(b"wav")
            return output_wav_path

        def fake_replace_video_audio(
            original_video_path,
            new_audio_path,
            output_video_path,
            ffmpeg_path="ffmpeg",
            subtitle_file_path=None,
            subtitle_font_name=None,
            subtitle_font_size=None,
            subtitle_margin_v=None,
        ):
            captured["subtitle_file_path"] = subtitle_file_path
            Path(output_video_path).write_bytes(b"final-video")
            return output_video_path

        monkeypatch.setattr(dubbing, "synthesize_khmer_tts", fake_synthesize_khmer_tts)
        monkeypatch.setattr(dubbing, "replace_video_audio", fake_replace_video_audio)

        result = generate_dubbed_video(
            original_video_path=str(original_video_path),
            khmer_script="\u179f\u17bd\u179f\u17d2\u178f\u17b8",
            output_dir=str(temp_dir / "output"),
            subtitle_segments=[
                {"id": 0, "start": 0.0, "end": 1.0, "text": "\u179f\u17bd\u179f\u17d2\u178f\u17b8"}
            ],
            burn_subtitles=True,
            temp_dir=str(temp_dir / "temp"),
            preserve_temp=False,
        )

        assert captured["subtitle_file_path"] is not None
        assert result["subtitle_path"] == captured["subtitle_file_path"]
        synth_path = result["synthesized_audio_path"]
        sub_path = result["subtitle_path"]
        assert synth_path is not None
        assert sub_path is not None
        assert not Path(synth_path).exists()
        assert not Path(sub_path).exists()

    def test_generate_dubbed_video_signature(self):
        """Validate generate_dubbed_video function signature."""
        import inspect

        sig = inspect.signature(generate_dubbed_video)
        assert "original_video_path" in sig.parameters
        assert "khmer_script" in sig.parameters
        assert "output_dir" in sig.parameters
        assert "subtitle_segments" in sig.parameters
        assert "burn_subtitles" in sig.parameters

    def test_synthesize_khmer_tts_uses_voxcpm2(self, temp_dir, monkeypatch):
        """VoxCPM2 defaults are passed to _save_voxcpm_audio; 48k intermediate file is cleaned up."""
        captured, fake_save_voxcpm_audio, fake_convert_audio_to_wav = make_fake_voxcpm_helpers()

        monkeypatch.setattr(dubbing, "_save_voxcpm_audio", fake_save_voxcpm_audio)
        monkeypatch.setattr(dubbing, "_convert_audio_to_wav", fake_convert_audio_to_wav)

        output_path = str(temp_dir / "output.wav")
        result = synthesize_khmer_tts("សួស្ដី", output_path)

        assert result == output_path
        assert captured["model_name"] == DEFAULT_VOXCPM_MODEL
        assert captured["cfg_value"] == DEFAULT_VOXCPM_CFG_VALUE
        assert captured["inference_timesteps"] == DEFAULT_VOXCPM_INFERENCE_TIMESTEPS

        # The _voxcpm_48k.wav intermediate file must not exist after the call
        from pathlib import Path as _Path
        intermediate = _Path(output_path).with_stem(_Path(output_path).stem + "_voxcpm_48k")
        assert not intermediate.exists()

    def test_synthesize_khmer_tts_ignores_voice_params(self, temp_dir, monkeypatch):
        """voice_name, rate, volume, pitch do not alter the _save_voxcpm_audio arguments."""
        captured, fake_save_voxcpm_audio, fake_convert_audio_to_wav = make_fake_voxcpm_helpers()

        monkeypatch.setattr(dubbing, "_save_voxcpm_audio", fake_save_voxcpm_audio)
        monkeypatch.setattr(dubbing, "_convert_audio_to_wav", fake_convert_audio_to_wav)

        # Baseline call with no override params
        synthesize_khmer_tts("សួស្ដី", str(temp_dir / "out1.wav"))
        baseline_model_name = captured["model_name"]
        baseline_cfg_value = captured["cfg_value"]
        baseline_inference_timesteps = captured["inference_timesteps"]

        # Call again with voice override params
        synthesize_khmer_tts(
            "សួស្ដី",
            str(temp_dir / "out2.wav"),
            voice_name="some-voice",
            rate="+10%",
            volume="+5%",
            pitch="+2Hz",
        )

        assert captured["model_name"] == baseline_model_name
        assert captured["cfg_value"] == baseline_cfg_value
        assert captured["inference_timesteps"] == baseline_inference_timesteps

    def test_synthesize_khmer_tts_cleans_up_on_error(self, temp_dir, monkeypatch):
        """The 48k intermediate WAV is deleted even when _convert_audio_to_wav raises."""
        from pathlib import Path as _Path

        output_path = str(temp_dir / "output.wav")
        intermediate = _Path(output_path).with_stem(_Path(output_path).stem + "_voxcpm_48k")

        def fake_save_creates_file(khmer_script, output_wav_path, model_name, device, cfg_value, inference_timesteps, load_denoiser=True):
            _Path(output_wav_path).write_bytes(b"fake-48k-wav")

        def fake_convert_raises(input_audio_path, output_wav_path, ffmpeg_path):
            raise RuntimeError("ffmpeg error")

        monkeypatch.setattr(dubbing, "_save_voxcpm_audio", fake_save_creates_file)
        monkeypatch.setattr(dubbing, "_convert_audio_to_wav", fake_convert_raises)

        with pytest.raises(RuntimeError):
            synthesize_khmer_tts("សួស្ដី", output_path)

        assert not intermediate.exists()

    def test_voxcpm2_module_constants_importable(self):
        """All VoxCPM2 module-level constants are importable with correct types."""
        assert isinstance(VOXCPM_AVAILABLE, bool)
        assert isinstance(DEFAULT_VOXCPM_MODEL, str) and DEFAULT_VOXCPM_MODEL
        assert isinstance(DEFAULT_VOXCPM_CFG_VALUE, float)
        assert isinstance(DEFAULT_VOXCPM_INFERENCE_TIMESTEPS, int)
        assert isinstance(DEFAULT_VOXCPM_DEVICE, str) and DEFAULT_VOXCPM_DEVICE
        assert isinstance(DEFAULT_VOXCPM_LOAD_DENOISER, bool)

    def test_load_voxcpm_model_caches_instance(self, monkeypatch):
        """_load_voxcpm_model returns a cached instance; from_pretrained is called only once."""
        import unittest.mock as mock

        mock_instance = mock.MagicMock()
        mock_voxcpm_cls = mock.MagicMock()
        mock_voxcpm_cls.from_pretrained.return_value = mock_instance

        # Reset the module-level cache before the test
        monkeypatch.setattr(dubbing, "VOXCPM_MODEL", None)
        monkeypatch.setattr(dubbing, "VOXCPM_AVAILABLE", True)
        monkeypatch.setattr(dubbing, "VoxCPM", mock_voxcpm_cls)

        result1 = _load_voxcpm_model(DEFAULT_VOXCPM_MODEL, DEFAULT_VOXCPM_DEVICE)
        result2 = _load_voxcpm_model(DEFAULT_VOXCPM_MODEL, DEFAULT_VOXCPM_DEVICE)

        assert result1 is result2
        mock_voxcpm_cls.from_pretrained.assert_called_once()

    def test_resolve_tts_setting_priority(self, monkeypatch):
        """Explicit value wins over env var; env var wins over default; default is last resort."""
        monkeypatch.setenv("TEST_ENV_VAR", "from-env")

        # Explicit value wins even when env var is set
        assert _resolve_tts_setting("explicit", "TEST_ENV_VAR", "default") == "explicit"

        # Env var wins when explicit is None
        assert _resolve_tts_setting(None, "TEST_ENV_VAR", "default") == "from-env"

        # Default returned when both explicit is None and env var is unset
        assert _resolve_tts_setting(None, "UNSET_ENV_VAR_XYZ", "default") == "default"

    def test_resolve_float_setting_invalid_env(self, monkeypatch):
        """_resolve_float_setting raises ValueError when env var is not a valid float."""
        monkeypatch.setenv("VOXCPM_CFG_TEST", "not-a-float")

        with pytest.raises(ValueError):
            _resolve_float_setting(None, "VOXCPM_CFG_TEST", 2.0)

    def test_resolve_int_setting_invalid_env(self, monkeypatch):
        """_resolve_int_setting raises ValueError when env var is not a valid integer."""
        monkeypatch.setenv("VOXCPM_INT_TEST", "not-an-int")

        with pytest.raises(ValueError):
            _resolve_int_setting(None, "VOXCPM_INT_TEST", 10)

    def test_resolve_bool_setting_truthy_values(self, monkeypatch):
        """_resolve_bool_setting returns True for all recognized truthy strings."""
        truthy_values = ["true", "1", "yes", "on"]

        for i, value in enumerate(truthy_values):
            env_name = f"VOXCPM_BOOL_TEST_{i}"
            monkeypatch.setenv(env_name, value)
            assert _resolve_bool_setting(None, env_name, False) is True

        # "false" should return False
        monkeypatch.setenv("VOXCPM_BOOL_FALSE_TEST", "false")
        assert _resolve_bool_setting(None, "VOXCPM_BOOL_FALSE_TEST", True) is False

    @given(st.text(alphabet=st.characters(whitelist_categories=("Zs", "Cc")), min_size=0))
    @settings(max_examples=200)
    def test_whitespace_input_raises_valueerror(self, whitespace_text):
        """Property: any whitespace-only or empty string raises ValueError.
        # Validates: Requirements 1.7, 2.1, 2.2
        """
        with pytest.raises(ValueError):
            synthesize_khmer_tts(whitespace_text, "/tmp/output_pbt.wav")

    @given(
        st.text(min_size=1).filter(lambda t: any(
            not (__import__('unicodedata').category(c) in ("Cc", "Zs", "Zl", "Zp") or c.isspace())
            for c in t
        )),
        st.from_regex(r"[A-Za-z0-9_]+\.wav", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_synthesize_returns_output_path(self, khmer_script, output_wav_filename):
        """Property: return value always equals output_wav_path when synthesis succeeds.
        # Validates: Requirements 2.3, 9.1
        """
        import tempfile
        from unittest.mock import patch
        from pathlib import Path

        def fake_save(khmer_script, output_wav_path, model_name, device, cfg_value, inference_timesteps, load_denoiser=True):
            Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_wav_path).write_bytes(b"fake-48k-wav")

        def fake_convert(input_audio_path, output_wav_path, ffmpeg_path):
            Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_wav_path).write_bytes(b"fake-44k-wav")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_wav_path = str(Path(tmp_dir) / output_wav_filename)
            with patch.object(dubbing, "_save_voxcpm_audio", fake_save), \
                 patch.object(dubbing, "_convert_audio_to_wav", fake_convert):
                result = synthesize_khmer_tts(khmer_script, output_wav_path)
                assert result == output_wav_path

    @given(
        st.text(min_size=1).filter(lambda s: bool(s.strip())),  # explicit_value — non-empty, non-whitespace-only; _resolve_tts_setting treats whitespace-only as absent
        st.text().filter(lambda s: "\x00" not in s),            # env_value — env vars cannot contain null chars
        st.text(),                                               # default_value
    )
    @settings(max_examples=200)
    def test_explicit_wins_resolver(self, explicit_value, env_value, default_value):
        """Property: explicit arg always returned by _resolve_tts_setting when non-empty.
        # Validates: Requirements 3.1, 9.2
        """
        import os
        env_name = "VOXCPM_EXPLICIT_WINS_TEST"
        original = os.environ.get(env_name)
        try:
            if env_value:
                os.environ[env_name] = env_value
            elif env_name in os.environ:
                del os.environ[env_name]
            result = _resolve_tts_setting(explicit_value, env_name, default_value)
            assert result == explicit_value.strip()
        finally:
            if original is not None:
                os.environ[env_name] = original
            elif env_name in os.environ:
                del os.environ[env_name]

    @given(
        st.floats(min_value=0, max_value=3600, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0, max_value=3600, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_srt_timestamp_monotonic(self, a, b):
        """Property: _format_srt_timestamp(a) <= _format_srt_timestamp(b) when a <= b (lexicographic order).
        # Validates: Requirements 9.3
        """
        if a > b:
            a, b = b, a  # ensure a <= b
        ts_a = _format_srt_timestamp(a)
        ts_b = _format_srt_timestamp(b)
        assert ts_a <= ts_b, f"_format_srt_timestamp({a}) = {ts_a!r} > _format_srt_timestamp({b}) = {ts_b!r}"

    @given(
        st.lists(
            st.fixed_dictionaries({
                "text": st.text(min_size=1).filter(lambda t: "\n" not in t and bool(t.strip())),
                "start": st.floats(min_value=0, max_value=3590, allow_nan=False, allow_infinity=False),
                "duration": st.floats(min_value=0.1, max_value=10, allow_nan=False, allow_infinity=False),
            }),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_srt_blank_line_structure(self, raw_segments):
        """Property: consecutive SRT entries are separated by exactly one blank line.
        # Validates: Requirements 9.4
        """
        import tempfile
        import os

        # Build properly ordered segments
        segments = []
        current_time = 0.0
        for i, seg in enumerate(raw_segments):
            start = current_time
            end = start + seg["duration"]
            segments.append({"id": i, "start": start, "end": end, "text": seg["text"]})
            current_time = end + 0.01  # small gap

        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name

        try:
            create_khmer_subtitle_file(segments, tmp_path)
            content = Path(tmp_path).read_text(encoding="utf-8")

            if len(segments) > 1:
                # Split on double newlines — each SRT entry should be separated by exactly \n\n
                # Strip trailing newline first so we don't get empty last entry
                entries = content.rstrip("\n").split("\n\n")
                assert len(entries) == len(segments), (
                    f"Expected {len(segments)} SRT entries, got {len(entries)}"
                )
                for entry in entries:
                    lines = entry.split("\n")
                    # Each entry: sequence number, timing line, text line(s)
                    assert len(lines) >= 3, f"SRT entry too short: {entry!r}"
        finally:
            os.unlink(tmp_path)

    @given(
        st.text(min_size=1).filter(lambda t: any(
            not (__import__('unicodedata').category(c) in ("Cc", "Zs", "Zl", "Zp") or c.isspace())
            for c in t
        )),
        st.one_of(st.none(), st.text(min_size=1)),   # voice_name
        st.one_of(st.none(), st.text(min_size=1)),   # rate
        st.one_of(st.none(), st.text(min_size=1)),   # volume
        st.one_of(st.none(), st.text(min_size=1)),   # pitch
    )
    @settings(max_examples=100)
    def test_ignored_params_idempotence(self, khmer_script, voice_name, rate, volume, pitch):
        """Property: _save_voxcpm_audio args are identical regardless of voice/rate/volume/pitch values.
        # Validates: Requirements 2.4, 7.2, 9.5
        """
        import tempfile
        from unittest.mock import patch
        from pathlib import Path

        calls = []

        def recording_save(khmer_script, output_wav_path, model_name, device, cfg_value, inference_timesteps, load_denoiser=True):
            calls.append({
                "khmer_script": khmer_script,
                "model_name": model_name,
                "cfg_value": cfg_value,
                "inference_timesteps": inference_timesteps,
            })
            Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_wav_path).write_bytes(b"fake-48k-wav")

        def fake_convert(input_audio_path, output_wav_path, ffmpeg_path):
            Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_wav_path).write_bytes(b"fake-44k-wav")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path1 = str(Path(tmp_dir) / "out1.wav")
            path2 = str(Path(tmp_dir) / "out2.wav")
            with patch.object(dubbing, "_save_voxcpm_audio", recording_save), \
                 patch.object(dubbing, "_convert_audio_to_wav", fake_convert):
                # Call with override params
                synthesize_khmer_tts(
                    khmer_script, path1,
                    voice_name=voice_name, rate=rate, volume=volume, pitch=pitch,
                )
                # Call without override params (all None)
                synthesize_khmer_tts(
                    khmer_script, path2,
                    voice_name=None, rate=None, volume=None, pitch=None,
                )

        assert len(calls) == 2
        assert calls[0]["khmer_script"] == calls[1]["khmer_script"]
        assert calls[0]["model_name"] == calls[1]["model_name"]
        assert calls[0]["cfg_value"] == calls[1]["cfg_value"]
        assert calls[0]["inference_timesteps"] == calls[1]["inference_timesteps"]

    @given(
        st.sampled_from(["true", "1", "yes", "on"]).flatmap(
            lambda s: st.lists(
                st.booleans(), min_size=len(s), max_size=len(s)
            ).map(lambda caps: "".join(c.upper() if cap else c for c, cap in zip(s, caps)))
        )
    )
    @settings(max_examples=200)
    def test_bool_resolver_truthy_strings(self, truthy_str):
        """Property: any capitalization of truthy strings ('true','1','yes','on') returns True.
        # Validates: Requirements 3.6
        """
        import os
        env_name = "VOXCPM_BOOL_TRUTHY_PBT_TEST"
        original = os.environ.get(env_name)
        try:
            os.environ[env_name] = truthy_str
            result = _resolve_bool_setting(None, env_name, False)
            assert result is True, f"Expected True for {truthy_str!r}, got {result!r}"
        finally:
            if original is not None:
                os.environ[env_name] = original
            elif env_name in os.environ:
                del os.environ[env_name]
