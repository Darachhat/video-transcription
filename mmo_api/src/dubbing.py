import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

VOXCPM_AVAILABLE: bool = False
VOXCPM_MODEL = None
try:
    from voxcpm import VoxCPM
    import soundfile as sf
    VOXCPM_AVAILABLE = True
except ImportError:
    VoxCPM = None
    sf = None

DEFAULT_VOXCPM_MODEL = "openbmb/VoxCPM2"
DEFAULT_VOXCPM_DEVICE = "auto"
DEFAULT_VOXCPM_CFG_VALUE = 2.5          # raised from 2.0 — stronger guidance = cleaner speech
DEFAULT_VOXCPM_INFERENCE_TIMESTEPS = 20  # raised from 10 — more diffusion steps = less noise
DEFAULT_VOXCPM_LOAD_DENOISER = True     # was False — denoiser removes background noise
DEFAULT_KHMER_SUBTITLE_FONT = "Leelawadee UI"
DEFAULT_KHMER_SUBTITLE_FONT_SIZE = 22
DEFAULT_KHMER_SUBTITLE_MARGIN_V = 28


def _resolve_tts_setting(value: Optional[str], env_name: str, default: str) -> str:
    """Resolve TTS configuration from explicit value, env var, or default."""
    if value and value.strip():
        return value.strip()
    return os.getenv(env_name, default).strip()


def _resolve_float_setting(value: Optional[float], env_name: str, default: float) -> float:
    """Resolve float configuration from explicit value, env var, or default."""
    if value is not None:
        return float(value)

    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default

    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a float, received {raw_value!r}") from exc


def _resolve_bool_setting(value: Optional[bool], env_name: str, default: bool) -> bool:
    """Resolve boolean configuration from explicit value, env var, or default."""
    if value is not None:
        return bool(value)

    raw_value = os.getenv(env_name, "").strip().lower()
    if not raw_value:
        return default

    return raw_value in ("true", "1", "yes", "on")


def _resolve_int_setting(value: Optional[int], env_name: str, default: int) -> int:
    """Resolve numeric configuration from explicit value, env var, or default."""
    if value is not None:
        return int(value)

    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer, received {raw_value!r}") from exc


def _load_voxcpm_model(model_name: str, device: str, load_denoiser: bool = True) -> VoxCPM:
    """Load VoxCPM2 model from HuggingFace. Cached globally to avoid reloading."""
    global VOXCPM_MODEL

    if VOXCPM_MODEL is not None:
        return VOXCPM_MODEL

    if not VOXCPM_AVAILABLE:
        raise ImportError("Install voxcpm to synthesize Khmer speech: pip install voxcpm")

    assert VoxCPM is not None

    effective_device = os.getenv("VOXCPM_DEVICE", device).strip() or device

    print(f"[TTS] Loading VoxCPM2 model {model_name} on device {effective_device} (denoiser={load_denoiser})...")
    t0 = time.perf_counter()

    VOXCPM_MODEL = VoxCPM.from_pretrained(
        model_name,
        device=effective_device,
        load_denoiser=load_denoiser,
        optimize=False,
    )

    print(f"[TTS] VoxCPM2 model ready on {effective_device} ({time.perf_counter() - t0:.1f}s)")
    return VOXCPM_MODEL


def _save_voxcpm_audio(
    khmer_script: str,
    output_wav_path: Path,
    model_name: str,
    device: str,
    cfg_value: float,
    inference_timesteps: int,
    load_denoiser: bool = True,
) -> None:
    """Synthesize Khmer speech to 48kHz WAV using VoxCPM2."""
    if not VOXCPM_AVAILABLE:
        raise ImportError("Install voxcpm to synthesize Khmer speech: pip install voxcpm")

    assert VoxCPM is not None
    assert sf is not None

    model = _load_voxcpm_model(model_name, device, load_denoiser=load_denoiser)

    print(f"[TTS] Generating audio with VoxCPM2 ({len(khmer_script)} chars)...")
    t0 = time.perf_counter()
    wav = model.generate(
        text=khmer_script,
        cfg_value=cfg_value,
        inference_timesteps=inference_timesteps,
        normalize=True,   # normalize Khmer text before synthesis for better accuracy
        denoise=load_denoiser,  # apply denoiser post-processing if model was loaded with it
    )
    print(f"[TTS] model.generate() done ({time.perf_counter() - t0:.1f}s)")

    print(f"[TTS] Writing 48kHz WAV to {output_wav_path}")
    t1 = time.perf_counter()
    sf.write(str(output_wav_path), wav, model.tts_model.sample_rate)
    print(f"[TTS] WAV write done ({time.perf_counter() - t1:.1f}s)")


def _convert_audio_to_wav(input_audio_path: Path, output_wav_path: Path, ffmpeg_path: str) -> None:
    """Convert an audio file to PCM WAV for downstream FFmpeg merge operations.

    Uses the 'soxr_hq' resampler (SoX Resampler, high quality) which produces
    significantly better results than FFmpeg's default linear resampler when
    downsampling from 48kHz to 44.1kHz.
    """
    result = subprocess.run(
        [
            ffmpeg_path, "-y",
            "-i", str(input_audio_path),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-resampler", "soxr",          # high-quality SoX resampler
            "-precision", "33",            # soxr highest precision (28=HQ, 33=VHQ)
            str(output_wav_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # soxr may not be available in all ffmpeg builds — fall back to default resampler
        result = subprocess.run(
            [
                ffmpeg_path, "-y",
                "-i", str(input_audio_path),
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                str(output_wav_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")


def _format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def create_khmer_subtitle_file(subtitle_segments: List[Dict[str, Any]], output_srt_path: str) -> str:
    """Write Khmer subtitle segments to a UTF-8 SRT file."""
    if not subtitle_segments:
        raise ValueError("Subtitle segments are empty")

    output_path = Path(output_srt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries: List[str] = []
    subtitle_index = 1
    for segment in subtitle_segments:
        text = str(segment.get("text", "")).replace("\r\n", "\n").strip()
        if not text:
            continue

        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        if end <= start:
            end = start + 0.5

        entries.extend(
            [
                str(subtitle_index),
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                text,
                "",
            ]
        )
        subtitle_index += 1

    if subtitle_index == 1:
        raise ValueError("Subtitle segments do not contain any text")

    output_path.write_text("\n".join(entries), encoding="utf-8")
    return str(output_path)


def _escape_ffmpeg_subtitle_path(subtitle_path: Path) -> str:
    """Escape a subtitle path for FFmpeg's subtitles filter."""
    escaped_path = subtitle_path.resolve().as_posix()
    escaped_path = escaped_path.replace(":", r"\:")
    escaped_path = escaped_path.replace("'", r"\'")
    return escaped_path


def _build_subtitle_filter(
    subtitle_file_path: str,
    subtitle_font_name: Optional[str],
    subtitle_font_size: Optional[int],
    subtitle_margin_v: Optional[int],
) -> str:
    """Build FFmpeg subtitles filter with Khmer-friendly default styling."""
    resolved_font_name = _resolve_tts_setting(
        subtitle_font_name,
        "KHMER_SUBTITLE_FONT",
        DEFAULT_KHMER_SUBTITLE_FONT,
    ).replace("'", r"\'")
    resolved_font_size = _resolve_int_setting(
        subtitle_font_size,
        "KHMER_SUBTITLE_FONT_SIZE",
        DEFAULT_KHMER_SUBTITLE_FONT_SIZE,
    )
    resolved_margin_v = _resolve_int_setting(
        subtitle_margin_v,
        "KHMER_SUBTITLE_MARGIN_V",
        DEFAULT_KHMER_SUBTITLE_MARGIN_V,
    )

    style = (
        f"FontName={resolved_font_name},FontSize={resolved_font_size},Alignment=2,"
        f"MarginV={resolved_margin_v},BorderStyle=1,Outline=2,Shadow=0"
    )
    escaped_path = _escape_ffmpeg_subtitle_path(Path(subtitle_file_path))
    return f"subtitles='{escaped_path}':force_style='{style}'"


def synthesize_khmer_tts(
    khmer_script: str,
    output_wav_path: str,
    use_local_tts: bool = False,
    voice_name: Optional[str] = None,
    rate: Optional[str] = None,
    volume: Optional[str] = None,
    pitch: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
) -> str:
    """Synthesize Khmer script to WAV using VoxCPM2.

    Args:
        khmer_script: Full Khmer text to synthesize
        output_wav_path: Path where to save the output WAV (will be 44.1kHz after resampling)
        use_local_tts: Ignored (retained for backward compatibility)
        voice_name: Ignored (VoxCPM2 uses reference audio for cloning, not voice names)
        rate, volume, pitch: Ignored (VoxCPM2 uses natural prosody inference)
        ffmpeg_path: Path to ffmpeg executable

    Returns:
        Path to the synthesized WAV file (44.1kHz, 16-bit PCM)
    """
    import unicodedata
    if not khmer_script or not khmer_script.strip() or all(
        unicodedata.category(c) in ("Cc", "Zs", "Zl", "Zp") or c.isspace()
        for c in khmer_script
    ):
        raise ValueError("Khmer script is empty")

    _ = use_local_tts
    _ = voice_name
    _ = rate
    _ = volume
    _ = pitch

    output_path = Path(output_wav_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # VoxCPM2 generates 48kHz natively; resample to 44.1kHz for FFmpeg compatibility
    wav_48khz_path = output_path.with_stem(output_path.stem + "_voxcpm_48k")
    resolved_ffmpeg_path = _resolve_tts_setting(ffmpeg_path, "FFMPEG_PATH", "ffmpeg")

    # Load VoxCPM2 config from env
    model_name = _resolve_tts_setting(None, "VOXCPM_MODEL", DEFAULT_VOXCPM_MODEL)
    device = _resolve_tts_setting(None, "VOXCPM_DEVICE", DEFAULT_VOXCPM_DEVICE)
    cfg_value = _resolve_float_setting(None, "VOXCPM_CFG_VALUE", DEFAULT_VOXCPM_CFG_VALUE)
    inference_timesteps = _resolve_int_setting(None, "VOXCPM_INFERENCE_TIMESTEPS", DEFAULT_VOXCPM_INFERENCE_TIMESTEPS)
    load_denoiser = _resolve_bool_setting(None, "VOXCPM_LOAD_DENOISER", DEFAULT_VOXCPM_LOAD_DENOISER)

    try:
        print(
            f"[TTS] Synthesizing {len(khmer_script)} chars with VoxCPM2 "
            f"(model={model_name}, cfg={cfg_value}, steps={inference_timesteps}, denoiser={load_denoiser})..."
        )

        _save_voxcpm_audio(
            khmer_script=khmer_script,
            output_wav_path=wav_48khz_path,
            model_name=model_name,
            device=device,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
            load_denoiser=load_denoiser,
        )

        if not wav_48khz_path.exists() or wav_48khz_path.stat().st_size == 0:
            raise RuntimeError("VoxCPM2 returned empty audio")

        wav_48k_size = wav_48khz_path.stat().st_size
        print(f"[TTS] VoxCPM2 generated 48kHz WAV: {wav_48k_size} bytes")

        # Resample 48kHz to 44.1kHz for FFmpeg compatibility
        print(f"[TTS] Resampling 48kHz → 44.1kHz via FFmpeg...")
        t_resample = time.perf_counter()
        _convert_audio_to_wav(wav_48khz_path, output_path, resolved_ffmpeg_path)
        print(f"[TTS] Resample done ({time.perf_counter() - t_resample:.1f}s)")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg audio resampling failed")

        wav_44k_size = output_path.stat().st_size
        print(f"[TTS] Resampled to 44.1kHz WAV: {wav_44k_size} bytes")
        return str(output_path)

    except Exception as exc:
        raise RuntimeError(f"VoxCPM2 synthesis failed: {exc}") from exc
    finally:
        # Cleanup 48kHz intermediate file
        if wav_48khz_path.exists():
            try:
                wav_48khz_path.unlink()
            except Exception:
                pass


def replace_video_audio(
    original_video_path: str,
    new_audio_path: str,
    output_video_path: str,
    ffmpeg_path: str = "ffmpeg",
    subtitle_file_path: Optional[str] = None,
    subtitle_font_name: Optional[str] = None,
    subtitle_font_size: Optional[int] = None,
    subtitle_margin_v: Optional[int] = None,
) -> str:
    """Strip original audio from video, optionally burn subtitles, and mux the final output."""
    orig_video = Path(original_video_path)
    new_audio = Path(new_audio_path)
    output_video = Path(output_video_path)

    if not orig_video.exists():
        raise FileNotFoundError(f"Original video not found: {original_video_path}")
    if not new_audio.exists():
        raise FileNotFoundError(f"New audio not found: {new_audio_path}")
    if subtitle_file_path and not Path(subtitle_file_path).exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_file_path}")

    output_video.parent.mkdir(parents=True, exist_ok=True)

    # Check file sizes for debugging
    video_size = orig_video.stat().st_size
    audio_size = new_audio.stat().st_size

    if audio_size == 0:
        raise RuntimeError(f"Audio file is empty: {new_audio_path}")

    print(f"[MERGE] Video: {video_size} bytes, Audio: {audio_size} bytes")

    # Get video and audio durations
    result_v = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(orig_video)],
        capture_output=True,
        text=True,
    )
    result_a = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(new_audio)],
        capture_output=True,
        text=True,
    )

    try:
        video_duration = float(result_v.stdout.strip())
        audio_duration = float(result_a.stdout.strip())
    except Exception:
        video_duration = None
        audio_duration = None

    if video_duration and audio_duration:
        print(f"[MERGE] Video duration: {video_duration:.2f}s, Audio duration: {audio_duration:.2f}s")

    subtitle_filter = None
    if subtitle_file_path:
        subtitle_filter = _build_subtitle_filter(
            subtitle_file_path=subtitle_file_path,
            subtitle_font_name=subtitle_font_name,
            subtitle_font_size=subtitle_font_size,
            subtitle_margin_v=subtitle_margin_v,
        )

    # Always use apad=whole_dur so the audio track is guaranteed to cover the
    # full video length.  whole_dur pads with silence until the audio reaches
    # exactly VIDEO_DURATION seconds; it is a no-op when the audio is already
    # longer, so this single branch handles every case correctly.
    if video_duration:
        command = [
            ffmpeg_path,
            "-y",
            "-i", str(orig_video),
            "-i", str(new_audio),
            "-filter_complex", f"[1:a]apad=whole_dur={video_duration:.6f}[a]",
            "-map", "0:v:0",
            "-map", "[a]",
        ]
    else:
        # ffprobe could not determine video duration — merge without padding
        # (fallback, should rarely happen)
        command = [
            ffmpeg_path,
            "-y",
            "-i", str(orig_video),
            "-i", str(new_audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
        ]

    if subtitle_filter:
        command.extend(
            [
                "-vf", subtitle_filter,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
            ]
        )
    else:
        command.extend(["-c:v", "copy"])

    command.extend(
        [
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_video),
        ]
    )

    print(f"[MERGE] Running FFmpeg merge...")
    t_merge = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        error_msg = f"ffmpeg merge failed with code {process.returncode}\n"
        error_msg += f"  Command: {' '.join(command)}\n"
        error_msg += f"  Video size: {video_size} bytes\n"
        error_msg += f"  Audio size: {audio_size} bytes\n"
        error_msg += f"  stderr: {process.stderr}\n"
        print(error_msg)
        raise RuntimeError(error_msg)

    # Verify output file was created
    if not output_video.exists() or output_video.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg produced empty output: {output_video_path}")

    output_size = output_video.stat().st_size
    print(f"[MERGE] Output created: {output_size} bytes ({time.perf_counter() - t_merge:.1f}s)")
    return str(output_video)


def cleanup_temp_files(paths: Optional[list[str]] = None) -> None:
    """Delete temp files from disk."""
    if not paths:
        return

    for p in paths:
        try:
            path_obj = Path(p)
            if path_obj.exists():
                path_obj.unlink()
        except Exception:
            pass


def generate_dubbed_video(
    original_video_path: str,
    khmer_script: str,
    output_dir: str = "output",
    preserve_temp: bool = False,
    ffmpeg_path: str = "ffmpeg",
    subtitle_segments: Optional[List[Dict[str, Any]]] = None,
    burn_subtitles: bool = True,
    subtitle_font_name: Optional[str] = None,
    subtitle_font_size: Optional[int] = None,
    subtitle_margin_v: Optional[int] = None,
    temp_dir: str = "temp_assets",
) -> Dict[str, Optional[str]]:
    """
    Full pipeline for generating dubbed video.

    Returns dict with:
      - output_video_path
      - synthesized_audio_path
      - original_video_path
      - subtitle_path
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    temp_dir_path = Path(temp_dir)
    temp_dir_path.mkdir(parents=True, exist_ok=True)
    temp_audio_path = temp_dir_path / f"dubbed_audio_{uuid.uuid4().hex}.wav"
    temp_subtitle_path = temp_dir_path / f"subtitles_{uuid.uuid4().hex}.srt"
    subtitle_file_path: Optional[str] = None

    try:
        print(f"[DUBBING] Starting dubbing pipeline ({len(khmer_script)} chars Khmer script)")
        t_total = time.perf_counter()

        print(f"[DUBBING] Step 1/3 — TTS synthesis")
        t_step = time.perf_counter()
        synthesized_audio = synthesize_khmer_tts(
            khmer_script,
            str(temp_audio_path),
            ffmpeg_path=ffmpeg_path,
        )
        print(f"[DUBBING] Step 1/3 done ({time.perf_counter() - t_step:.1f}s)")

        if burn_subtitles and subtitle_segments:
            print(f"[DUBBING] Step 2/3 — Writing SRT ({len(subtitle_segments)} segments)")
            t_step = time.perf_counter()
            subtitle_file_path = create_khmer_subtitle_file(subtitle_segments, str(temp_subtitle_path))
            print(f"[DUBBING] Step 2/3 done ({time.perf_counter() - t_step:.1f}s)")
        else:
            print(f"[DUBBING] Step 2/3 — Skipped (burn_subtitles={burn_subtitles})")

        final_video_name = f"dubbed_{uuid.uuid4().hex}.mp4"
        final_video_path = output_dir_path / final_video_name

        print(f"[DUBBING] Step 3/3 — FFmpeg merge into {final_video_name}")
        t_step = time.perf_counter()
        merged_video = replace_video_audio(
            original_video_path=str(original_video_path),
            new_audio_path=synthesized_audio,
            output_video_path=str(final_video_path),
            ffmpeg_path=ffmpeg_path,
            subtitle_file_path=subtitle_file_path,
            subtitle_font_name=subtitle_font_name,
            subtitle_font_size=subtitle_font_size,
            subtitle_margin_v=subtitle_margin_v,
        )
        print(f"[DUBBING] Step 3/3 done ({time.perf_counter() - t_step:.1f}s)")

        print(f"[DUBBING] All steps complete — total {time.perf_counter() - t_total:.1f}s")

        if not preserve_temp:
            cleanup_temp_files([path for path in [synthesized_audio, subtitle_file_path] if path])

        return {
            "output_video_path": merged_video,
            "synthesized_audio_path": synthesized_audio,
            "original_video_path": str(original_video_path),
            "subtitle_path": subtitle_file_path,
        }

    except Exception as exc:
        if not preserve_temp:
            cleanup_temp_files(
                [
                    path
                    for path in [str(temp_audio_path), str(temp_subtitle_path) if temp_subtitle_path.exists() else None]
                    if path
                ]
            )
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate dubbed video with Khmer TTS")
    parser.add_argument("original_video", help="Original downloaded video path")
    parser.add_argument("khmer_script", help="Translated Khmer script")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--ffmpeg-path", default="ffmpeg", help="Path to ffmpeg binary")
    args = parser.parse_args()

    result = generate_dubbed_video(
        original_video_path=args.original_video,
        khmer_script=args.khmer_script,
        output_dir=args.output_dir,
        ffmpeg_path=args.ffmpeg_path,
        preserve_temp=False,
    )

    print(result)
