import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Optional

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


def synthesize_khmer_tts(
    khmer_script: str,
    output_wav_path: str,
    use_local_tts: bool = False,
    voice_name: str = "km-KH-Wavenet-A",
) -> str:
    """Synthesize Khmer script to WAV using gTTS (free, smooth) or pyttsx3 (offline).
    
    gTTS with slow=True: Free, smooth pronunciation, supports Khmer
    pyttsx3: Free offline, unreliable on Windows in scripts
    """
    if not khmer_script or not khmer_script.strip():
        raise ValueError("Khmer script is empty")

    output_path = Path(output_wav_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not use_local_tts and GTTS_AVAILABLE:
        # Use gTTS with slow=True for smooth, clear pronunciation
        try:
            print(f"[TTS] Synthesizing {len(khmer_script)} chars with gTTS (slow mode for smooth audio)...")
            mp3_path = Path(output_wav_path).with_suffix(".mp3")
            # slow=True makes pronunciation slower and clearer
            tts = gTTS(text=khmer_script, lang='km', slow=True)
            tts.save(str(mp3_path))
            
            if not mp3_path.exists() or mp3_path.stat().st_size == 0:
                raise RuntimeError("gTTS returned empty audio")

            mp3_size = mp3_path.stat().st_size
            print(f"[TTS] gTTS generated MP3: {mp3_size} bytes")
            
            # Convert MP3 to WAV using ffmpeg
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), "-acodec", "pcm_s16le", "-ar", "44100", str(output_path)],
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                print(f"[TTS] FFmpeg stderr:\n{result.stderr}")
                raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
            
            # Clean up MP3
            mp3_path.unlink()
            
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("FFmpeg audio conversion failed")
            
            wav_size = output_path.stat().st_size
            print(f"[TTS] Converted to WAV: {wav_size} bytes")
            return str(output_path)
        except Exception as exc:
            raise RuntimeError(f"gTTS failed: {exc}") from exc

    elif use_local_tts and PYTTSX3_AVAILABLE:
        # Use pyttsx3 (free offline, but unreliable on Windows in scripts)
        try:
            engine = pyttsx3.init()
            # Set rate and volume for better quality
            engine.setProperty("rate", 150)
            engine.setProperty("volume", 0.9)
            engine.save_to_file(khmer_script, str(output_path))
            engine.runAndWait()
            
            # Validate file was created and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"pyttsx3 failed to generate audio file")
            
            return str(output_path)
        except Exception as exc:
            raise RuntimeError(f"pyttsx3 TTS failed: {exc}") from exc

    else:
        raise ImportError(
            "Install Bark for best Khmer TTS quality:\n"
            "  pip install bark-tts\n"
            "Or install gTTS for free alternative:\n"
            "  pip install gtts\n"
            "Or fallback to pyttsx3:\n"
            "  pip install pyttsx3"
        )


def replace_video_audio(original_video_path: str, new_audio_path: str, output_video_path: str, ffmpeg_path: str = "ffmpeg") -> str:
    """Strip original audio from video and replace with new audio track using ffmpeg."""
    orig_video = Path(original_video_path)
    new_audio = Path(new_audio_path)
    output_video = Path(output_video_path)

    if not orig_video.exists():
        raise FileNotFoundError(f"Original video not found: {original_video_path}")
    if not new_audio.exists():
        raise FileNotFoundError(f"New audio not found: {new_audio_path}")

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
    except:
        video_duration = None
        audio_duration = None
    
    if video_duration and audio_duration:
        print(f"[MERGE] Video duration: {video_duration:.2f}s, Audio duration: {audio_duration:.2f}s")
    
    # FFmpeg command to replace audio with padding if needed
    if video_duration and audio_duration and audio_duration < video_duration:
        # Audio is shorter, pad it
        pad_duration = video_duration - audio_duration + 1
        command = [
            ffmpeg_path,
            "-y",
            "-i", str(orig_video),
            "-i", str(new_audio),
            "-filter_complex", f"[1:a]apad=pad_dur={pad_duration}[a]",
            "-map", "0:v:0",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_video),
        ]
    else:
        # Audio is long enough, just merge
        command = [
            ffmpeg_path,
            "-y",
            "-i", str(orig_video),
            "-i", str(new_audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(output_video),
        ]

    print(f"[MERGE] Running FFmpeg merge...")
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
    print(f"[MERGE] Output created: {output_size} bytes")
    return str(output_video)


def cleanup_temp_files(paths: Optional[list] = None) -> None:
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
) -> Dict[str, str]:
    """
    Full pipeline for generating dubbed video.

    Returns dict with:
      - output_video_path
      - synthesized_audio_path
      - original_video_path
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    temp_audio_path = Path("temp_assets") / f"dubbed_audio_{uuid.uuid4().hex}.wav"

    try:
        synthesized_audio = synthesize_khmer_tts(khmer_script, str(temp_audio_path))

        final_video_name = f"dubbed_{uuid.uuid4().hex}.mp4"
        final_video_path = output_dir_path / final_video_name

        merged_video = replace_video_audio(
            original_video_path=str(original_video_path),
            new_audio_path=synthesized_audio,
            output_video_path=str(final_video_path),
            ffmpeg_path=ffmpeg_path,
        )

        if not preserve_temp:
            cleanup_temp_files([synthesized_audio])

        return {
            "output_video_path": merged_video,
            "synthesized_audio_path": synthesized_audio,
            "original_video_path": str(original_video_path),
        }

    except Exception as exc:
        if not preserve_temp and temp_audio_path.exists():
            cleanup_temp_files([str(temp_audio_path)])
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
