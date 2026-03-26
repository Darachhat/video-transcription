import os
from pathlib import Path
from typing import Dict, Optional

import yt_dlp


def download_video_and_audio(url: str, output_dir: str = "temp_assets") -> Dict[str, str]:
    """Download best video and separate WAV audio via yt-dlp.

    Returns a dict with keys: video_path, audio_path.
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # video will be downloaded to best available format; audio converted to WAV
    # use template to avoid collisions
    base_template = str(output_dir_path / "%(title).200s-%(id)s")

    video_opts = {
        "format": "bv[ext=mp4]+ba[ext=m4a]/best",  # best video+best audio fallback
        "outtmpl": base_template + ".%(ext)s",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    audio_opts = {
        "format": "bestaudio/best",
        "outtmpl": base_template + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            # Use prepare_filename to get the exact path yt-dlp intended
            expected_video_path = Path(ydl.prepare_filename(info))
            # The actual extension might have changed if merged
            if not expected_video_path.exists():
                # Try finding it with common extensions if the exact path doesn't exist
                video_path = None
                for ext in ["mp4", "mkv", "webm", "mov"]:
                    candidate = expected_video_path.with_suffix(f".{ext}")
                    if candidate.exists():
                        video_path = str(candidate)
                        break
            else:
                video_path = str(expected_video_path)

        # Next download audio-only WAV
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            audio_info = ydl.extract_info(url, download=True)
            # For audio with postprocessor, the final path is usually .wav
            expected_audio_path = Path(ydl.prepare_filename(audio_info)).with_suffix(".wav")
            
            if expected_audio_path.exists():
                audio_path = str(expected_audio_path)
            else:
                # Fallback search
                audio_path = None
                for candidate in output_dir_path.glob(f"*{video_id}*.wav"):
                    audio_path = str(candidate)
                    break

        if not video_path or not audio_path:
            raise FileNotFoundError(f"Unable to locate downloaded video ({video_path}) or audio ({audio_path}) paths for ID {video_id}")

        return {"video_path": video_path, "audio_path": audio_path}

    except Exception as exc:
        raise RuntimeError(f"Video/audio download failed: {exc}") from exc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download video + WAV audio using yt-dlp")
    parser.add_argument("url", help="Video URL to download")
    parser.add_argument("--output-dir", default="temp_assets", help="Temp download directory")
    args = parser.parse_args()

    result = download_video_and_audio(args.url, args.output_dir)
    print(result)