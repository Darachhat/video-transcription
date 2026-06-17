# Automated Video Translation and Dubbing Pipeline

## Overview

This repo provides a modular pipeline to:

1. Download video and audio using `yt-dlp`
2. Transcribe audio locally with OpenAI Whisper
3. Translate the transcript into Khmer with Google Gemini
4. Generate Khmer speech with `edge-tts`
5. Translate Whisper segments into timed Khmer subtitles
6. Merge the synthesized audio back into the source video and burn Khmer subtitles with FFmpeg

## Setup

1. Create a Python 3.10+ virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`
4. Set the required environment variables for translation and media tooling

## Environment Variables

```env
GOOGLE_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
# Optional fallback chain when a model is unavailable or out of quota
# GEMINI_MODELS=gemini-2.5-flash,gemini-2.5-pro
# Optional Vertex AI / google-genai configuration
# GOOGLE_APPLICATION_CREDENTIALS=path/to/your-service-account.json
# GOOGLE_GENAI_USE_VERTEXAI=true
# GOOGLE_CLOUD_PROJECT=your-gcp-project
# GOOGLE_CLOUD_LOCATION=us-central1
FFMPEG_PATH=ffmpeg
EDGE_TTS_VOICE=km-KH-SreymomNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_VOLUME=+0%
EDGE_TTS_PITCH=+0Hz
KHMER_SUBTITLE_FONT=Leelawadee UI
KHMER_SUBTITLE_FONT_SIZE=22
KHMER_SUBTITLE_MARGIN_V=28
OUTPUT_DIR=output
TEMP_DIR=temp_assets
```

`edge-tts` supports Khmer neural voices such as `km-KH-SreymomNeural` and `km-KH-PisethNeural`.
The subtitle burn-in step uses FFmpeg/libass, so the configured font should support Khmer glyphs on the machine running the pipeline.

## Quick Run

```bash
python -m src.pipeline "https://www.youtube.com/watch?v=<id>"
```

To keep the dubbed video without burned-in Khmer subtitles:

```bash
python -m src.pipeline "https://www.youtube.com/watch?v=<id>" --no-subtitles
```

## Modules

- `src/downloader.py`
- `src/transcription.py`
- `src/translator.py`
- `src/dubbing.py`
- `src/pipeline.py`

## Notes

- Ensure `ffmpeg` and `ffprobe` are available in `PATH`, or set `FFMPEG_PATH`.
- The translation step depends on Gemini credentials and will now try the configured model list in order, defaulting to `gemini-2.5-flash` before `gemini-2.5-pro`.
- The Khmer speech step now uses Edge-TTS instead of Google Cloud TTS or gTTS.
- Subtitle timings come from Whisper segments, and the final video now includes burned-in Khmer subtitles by default.
