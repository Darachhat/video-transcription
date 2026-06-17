import os
from pathlib import Path
from typing import Any, Dict, List, cast

import whisper


def transcribe_audio(audio_path: str, model_size: str = "base") -> Dict[str, Any]:
    """Transcribe WAV audio using OpenAI Whisper local model.

    Returns:
      {
        "language": "en",
        "transcript": "full transcript text",
        "segments": [{"start": 0.0, "end": 1.2, "text": "...", "id": 0}, ...]
      }
    """
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    try:
        model = whisper.load_model(model_size)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Whisper model '{model_size}': {exc}") from exc

    try:
        result = model.transcribe(str(audio_file), verbose=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to transcribe audio '{audio_path}': {exc}") from exc

    language = result.get("language")
    text = str(result.get("text", "")).strip()
    raw_segments: List[Dict[str, Any]] = cast(List[Dict[str, Any]], result.get("segments", []))

    segments: List[Dict[str, Any]] = []
    for segment in raw_segments:
        segments.append(
            {
                "id": segment.get("id"),
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": segment.get("text", "").strip(),
            }
        )

    return {
        "language": language,
        "transcript": text,
        "segments": segments,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe WAV with Whisper")
    parser.add_argument("audio_path", help="Path to WAV audio file")
    parser.add_argument("--model", default="base", help="Whisper model size")
    args = parser.parse_args()

    print(transcribe_audio(args.audio_path, model_size=args.model))
