import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

from .downloader import download_video_and_audio
from .transcription import transcribe_audio
from .translator import translate_segments_to_khmer_subtitles, translate_to_khmer_script
from .dubbing import generate_dubbed_video


def run_automated_dubbing_pipeline(
    video_url: str,
    temp_dir: str = "temp_assets",
    output_dir: str = "output",
    whisper_model: str = "base",
    ffmpeg_path: str = "ffmpeg",
    preserve_temp_files: bool = False,
    burn_subtitles: bool = True,
) -> Dict[str, Any]:
    """Run the full automated video translation and dubbing pipeline."""
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Download video + audio
    downloaded = download_video_and_audio(video_url, output_dir=temp_dir)
    video_path = downloaded["video_path"]
    audio_path = downloaded["audio_path"]

    # Transcribe with Whisper
    transcript_data = transcribe_audio(audio_path, model_size=whisper_model)

    # Translate into Khmer script with Gemini
    khmer_translation = translate_to_khmer_script(
        transcript_data["transcript"], source_lang=transcript_data.get("language", "auto")
    )
    subtitle_translation = translate_segments_to_khmer_subtitles(
        transcript_data.get("segments", []),
        source_lang=transcript_data.get("language", "auto"),
    )

    # Generate dubbed video with TTS, timed Khmer subtitles, and merge
    dubbing_result = generate_dubbed_video(
        original_video_path=video_path,
        khmer_script=khmer_translation["khmer_script"],
        output_dir=output_dir,
        preserve_temp=preserve_temp_files,
        ffmpeg_path=ffmpeg_path,
        subtitle_segments=subtitle_translation["segments"],
        burn_subtitles=burn_subtitles,
        temp_dir=temp_dir,
    )

    return {
        "downloaded": downloaded,
        "transcription": transcript_data,
        "translation": khmer_translation,
        "subtitle_translation": subtitle_translation,
        "dubbing": dubbing_result,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Automated Video Translation + Dubbing Pipeline")
    parser.add_argument("video_url", help="Video URL to process")
    parser.add_argument("--temp-dir", default="temp_assets", help="Temp assets folder")
    parser.add_argument("--output-dir", default="output", help="Final output folder")
    parser.add_argument("--model", default="base", help="Whisper model size")
    parser.add_argument("--ffmpeg-path", default="ffmpeg", help="Path to ffmpeg executable")
    parser.add_argument("--preserve-temp", action="store_true", help="Keep temp WAV assets")
    parser.add_argument("--no-subtitles", action="store_true", help="Disable burned-in Khmer subtitles")

    args = parser.parse_args()

    try:
        result = run_automated_dubbing_pipeline(
            video_url=args.video_url,
            temp_dir=args.temp_dir,
            output_dir=args.output_dir,
            whisper_model=args.model,
            ffmpeg_path=args.ffmpeg_path,
            preserve_temp_files=args.preserve_temp,
            burn_subtitles=not args.no_subtitles,
        )
    except Exception as exc:
        raise SystemExit(f"[ERROR] {exc}") from exc

    # Print output paths (avoid Khmer character encoding issues)
    print("\n[SUCCESS] Pipeline completed successfully!")
    print(f"Output video: {result['dubbing']['output_video_path']}")
    print(f"Synthesized audio: {result['dubbing']['synthesized_audio_path']}")
