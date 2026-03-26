# Required Technical Stack & Capabilities

## Core Infrastructure
* **Python:** The backbone of the orchestration logic.
* **FFmpeg:** Command-line tool for all media manipulation (extracting `.wav`, stripping audio, merging new audio tracks).

## Libraries & External APIs
* **yt-dlp:** For handling bulk video downloads and bypassing platform restrictions.
* **OpenAI Whisper (Local):** Utilizing the `openai-whisper` Python package to run speech-to-text and language detection locally.
* **Google Gemini API:** Using prompt engineering to translate transcripts into engaging, social-media-ready Khmer storytelling formats.
* **Google Cloud Text-to-Speech (TTS):** Utilizing the `google-cloud-texttospeech` package to synthesize the Khmer text (`km-KH` locale) into audio files.

## Specialized Knowledge Required
* Handling asynchronous requests and bulk file processing in Python.
* Managing GPU memory allocation for running PyTorch/Whisper locally.
* Manipulating `.srt` or `.vtt` timestamp data to ensure generated audio matches the video timing.