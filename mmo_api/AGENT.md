# Agent Persona: Video Pipeline Architect

## Role
You are an expert backend engineer and AI integration specialist. Your objective is to assist in building a fully automated, scalable Python pipeline for video downloading, transcription, translation, and dubbing.

## Project Scope: Automated Video Dubbing Pipeline
The application processes videos in bulk through the following sequential stages:
1. **Retrieval:** Downloading videos from target platforms.
2. **Extraction:** Separating audio tracks from the video.
3. **Transcription:** Detecting the source language and generating exact text timestamps.
4. **Creative Translation:** Transforming the text into engaging, localized Khmer scripts with storytelling hooks.
5. **Synthesis:** Generating high-quality Khmer audio from the translated text.
6. **Merging:** Replacing the original audio track with the newly generated Khmer audio.

## Design Philosophy
* Ensure each step of the pipeline is isolated so components can be swapped or tested independently.
* Prioritize local processing where possible to reduce API costs.
* Manage temporary files cleanly (e.g., deleting intermediate `.wav` or `.srt` files after the final video is rendered).

---

## Project Memory

### Directory Layout
```
mmo-tool/
├── src/
│   ├── __init__.py
│   ├── pipeline.py          # Orchestrator — run_automated_dubbing_pipeline()
│   ├── downloader.py        # yt-dlp wrapper — download_video_and_audio()
│   ├── transcription.py     # Whisper wrapper — transcribe_audio()
│   ├── translator.py        # Gemini wrapper — translate_to_khmer_script(), translate_segments_to_khmer_subtitles()
│   ├── dubbing.py           # TTS + merge — synthesize_khmer_tts(), replace_video_audio(), generate_dubbed_video()
│   ├── audio_separator.py   # Optional vocal/music split — separate_audio() (not wired into pipeline yet)
│   └── utils.py             # setup_logger(), retry_on_exception() decorator
├── tests/
│   ├── conftest.py          # Shared fixtures: temp_dir, sample_audio_path, sample_video_path, sample_transcript
│   ├── test_downloader.py
│   ├── test_transcription.py
│   ├── test_translator.py
│   ├── test_dubbing.py
│   └── test_pipeline.py
├── secrets/                 # Gitignored — holds service-account JSONs
├── output/                  # Final dubbed MP4s (gitignored)
├── temp_assets/             # Intermediate WAV/SRT files (gitignored)
├── requirements.txt
├── pytest.ini
├── README.md
├── CLAUDE.md                # AI communication style guide
└── SKILL.md                 # Tech stack reference
```

---

### Module-by-Module Reference

#### `src/pipeline.py` — Orchestrator
- **Entry point:** `python -m src.pipeline "<url>" [--temp-dir] [--output-dir] [--model base|small|medium|large] [--ffmpeg-path] [--preserve-temp] [--no-subtitles]`
- **Public API:** `run_automated_dubbing_pipeline(video_url, temp_dir, output_dir, whisper_model, ffmpeg_path, preserve_temp_files, burn_subtitles) -> Dict`
- **Return keys:** `downloaded`, `transcription`, `translation`, `subtitle_translation`, `dubbing`
- Calls `download_video_and_audio` → `transcribe_audio` → `translate_to_khmer_script` + `translate_segments_to_khmer_subtitles` → `generate_dubbed_video`
- Passes `subtitle_segments` (from subtitle translation) and `burn_subtitles` flag into `generate_dubbed_video`
- Defaults: `temp_dir="temp_assets"`, `output_dir="output"`, `whisper_model="base"`, `burn_subtitles=True`

#### `src/downloader.py` — yt-dlp Wrapper
- **Public API:** `download_video_and_audio(url, output_dir="temp_assets") -> {"video_path": str, "audio_path": str}`
- Downloads best video (mp4+m4a merged) and separately extracts WAV audio via `FFmpegExtractAudio` postprocessor.
- Uses filename template `%(title).200s-%(id)s` to avoid collisions.
- Falls back to extension scanning (`mp4/mkv/webm/mov`) if `prepare_filename()` path doesn't exist.
- Raises `RuntimeError("Video/audio download failed: ...")` on any error.

#### `src/transcription.py` — Whisper Wrapper
- **Public API:** `transcribe_audio(audio_path, model_size="base") -> {"language": str, "transcript": str, "segments": List[Dict]}`
- Each segment: `{"id": int, "start": float, "end": float, "text": str}`
- Raises `FileNotFoundError` if audio file doesn't exist; `RuntimeError` on model load or transcription failure.
- Model sizes: `tiny`, `base`, `small`, `medium`, `large` (tradeoff: speed vs. accuracy).

#### `src/translator.py` — Gemini Translation
- **Public APIs:**
  - `translate_to_khmer_script(transcript, source_lang="auto") -> {"source_language", "khmer_script", "raw_response", "models_used"}`
  - `translate_segments_to_khmer_subtitles(segments, source_lang="auto") -> {"source_language", "segments", "raw_response", "models_used"}`
- **Chunking:** `_chunk_text(text, max_chunk_size=1500)` splits large transcripts by paragraph, then sentence. Each chunk is translated separately and rejoined with `\n\n`.
- **Model resolution order:** `GEMINI_MODELS` (comma-separated list) → `GEMINI_MODEL` (single) → hardcoded `("gemini-2.5-flash", "gemini-2.5-pro")`
- **SDK dual-path:** Uses `google-genai` (modern, `client_kind="modern"`) when available, falls back to `google.generativeai` (legacy, `client_kind="legacy"`). Vertex AI supported via `GOOGLE_GENAI_USE_VERTEXAI=true` + `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION`.
- **Model fallback logic:** `_translate_with_model_fallback()` iterates model list; falls back on quota errors (`ResourceExhausted`, 429, `quota exceeded`, `resource_exhausted`, `rate limit`), 404, or permission errors.
- **Subtitle translation robustness:** 3-tier fault recovery — (1) parse JSON batch, (2) `_repair_subtitle_translation_batch()` sends malformed response back to model, (3) `_translate_subtitle_segments_line_by_line()` for segment-by-segment fallback.
- **Credential check:** `_ensure_gemini_credentials()` raises `EnvironmentError` if neither `GOOGLE_API_KEY`/`GEMINI_API_KEY` nor Vertex AI env vars are set.
- **Generation config:** `temperature=0.3`, `max_output_tokens=2048`.
- **Subtitle segment batching:** `_chunk_subtitle_segments()` groups segments into batches to stay within model input limits.

#### `src/dubbing.py` — TTS + FFmpeg Merge
- **Public APIs:**
  - `synthesize_khmer_tts(khmer_script, output_wav_path, voice_name=None, rate=None, volume=None, pitch=None, ffmpeg_path="ffmpeg", ...) -> str  # voice_name/rate/volume/pitch are backward-compat no-ops`
  - `create_khmer_subtitle_file(subtitle_segments, output_srt_path) -> str`
  - `replace_video_audio(original_video_path, new_audio_path, output_video_path, ffmpeg_path, subtitle_file_path, ...) -> str`
  - `generate_dubbed_video(...) -> {"output_video_path", "synthesized_audio_path", "original_video_path", "subtitle_path"}`
  - `cleanup_temp_files(paths) -> None`
- **Module-level flag:** `VOXCPM_AVAILABLE: bool` — `True` when `voxcpm` and `soundfile` are importable; `False` otherwise.
- **Model config constants:** `DEFAULT_VOXCPM_MODEL` (`openbmb/VoxCPM2`), `DEFAULT_VOXCPM_DEVICE` (`auto`), `DEFAULT_VOXCPM_CFG_VALUE` (`2.0`), `DEFAULT_VOXCPM_INFERENCE_TIMESTEPS` (`10`), `DEFAULT_VOXCPM_LOAD_DENOISER` (`False`).
- **Public API note:** `voice_name`, `rate`, `volume`, and `pitch` parameters in `synthesize_khmer_tts()` are retained for backward compatibility but are **no-ops** with VoxCPM2.
- **Internal helpers:** `_save_voxcpm_audio(khmer_script, output_wav_path, model_name, device, cfg_value, inference_timesteps)` — calls VoxCPM2 to write 48 kHz WAV; `_load_voxcpm_model(model_name, device)` — loads and caches the VoxCPM2 model singleton; `_convert_audio_to_wav(input_audio_path, output_wav_path, ffmpeg_path)` — FFmpeg resampling.
- **TTS flow:** VoxCPM2 generates 48 kHz WAV (`*_voxcpm_48k.wav`) → FFmpeg resamples to 44.1 kHz → intermediate 48 kHz file deleted in `finally` block.
- **Audio padding:** If dubbed audio is shorter than video, uses `apad=pad_dur=N` filter so video isn't truncated.
- **Subtitle burn-in:** FFmpeg `subtitles=` filter with `libx264` re-encode (`-preset medium -crf 18 -pix_fmt yuv420p`). No subtitle = `-c:v copy`.
- **Subtitle font defaults:** `Leelawadee UI`, size `22`, `MarginV=28`. Override via `KHMER_SUBTITLE_FONT`, `KHMER_SUBTITLE_FONT_SIZE`, `KHMER_SUBTITLE_MARGIN_V`.
- **SRT paths on Windows:** `_escape_ffmpeg_subtitle_path()` converts to POSIX and escapes `:` and `'`.
- **Output naming:** `dubbed_<uuid>.mp4` in `output/`; temp files use `uuid.uuid4().hex` names in `temp_assets/`.
- **Temp cleanup:** Controlled by `preserve_temp` flag. Deletes both the WAV audio and SRT file after successful merge.

#### `src/audio_separator.py` — Vocal/Instrumental Split (Optional)
- **Not currently wired into the main pipeline.**
- **Public API:** `separate_audio(audio_path, output_dir="temp_assets/separated") -> {"vocals": str, "music": str}`
- Uses `audio-separator` CLI with model `UVR-MDX-NET-Voc_FT.onnx`.
- Scans output directory for files containing `Vocals` or `Instrumental` in their name.

#### `src/utils.py` — Shared Utilities
- `setup_logger(name, level=logging.INFO) -> Logger` — standard formatter with timestamp.
- `retry_on_exception(max_retries=3, delay=1.0, backoff=2.0, exceptions=(Exception,))` — exponential backoff decorator.

---

### Environment Variables (`.env`)
| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | — | Gemini API authentication |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Single model override |
| `GEMINI_MODELS` | — | Comma-separated fallback chain (e.g. `gemini-2.5-flash,gemini-2.5-pro`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Service account JSON for Vertex AI |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Enable Vertex AI mode |
| `GOOGLE_CLOUD_PROJECT` | — | GCP project for Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | — | Region for Vertex AI |
| `FFMPEG_PATH` | `ffmpeg` | Custom FFmpeg binary path |
| `VOXCPM_MODEL` | `openbmb/VoxCPM2` | HuggingFace model ID for VoxCPM2 |
| `VOXCPM_DEVICE` | `auto` | PyTorch device (`cpu`, `cuda`, `auto`) |
| `VOXCPM_CFG_VALUE` | `2.0` | Classifier-free guidance scale |
| `VOXCPM_INFERENCE_TIMESTEPS` | `10` | Diffusion sampling steps |
| `VOXCPM_LOAD_DENOISER` | `false` | Load optional denoiser model |
| `KHMER_SUBTITLE_FONT` | `Leelawadee UI` | Subtitle burn-in font (must support Khmer) |
| `KHMER_SUBTITLE_FONT_SIZE` | `22` | Subtitle font size |
| `KHMER_SUBTITLE_MARGIN_V` | `28` | Subtitle vertical margin |
| `OUTPUT_DIR` | `output` | Final output directory |
| `TEMP_DIR` | `temp_assets` | Intermediate file directory |

---

### Dependencies (`requirements.txt`)
| Package | Purpose |
|---|---|
| `yt-dlp>=2025.2.4` | Video/audio download |
| `openai-whisper>=2023.8.0` | Local STT + language detection |
| `google-genai>=1.0.0` | Modern Gemini SDK (primary) |
| `google-generativeai>=0.1.0` | Legacy Gemini SDK (fallback) |
| `voxcpm>=1.0.0` | VoxCPM2 neural TTS (Khmer speech synthesis) |
| `soundfile>=0.12.0` | Write 48 kHz WAV output from VoxCPM2 |
| `python-dotenv>=1.0.0` | `.env` loading |
| `ffmpeg-python>=0.2.0` | FFmpeg bindings (subprocess used directly in practice) |
| `pydub>=0.25.1` | Audio utilities |
| `requests>=2.31.0` | HTTP requests |
| `pytest>=7.4.0` + `pytest-cov>=4.1.0` | Testing |

**System requirements:** `ffmpeg` + `ffprobe` in PATH (or via `FFMPEG_PATH`), PyTorch for Whisper.

---

### Testing Conventions
- Run all tests: `pytest` (configured in `pytest.ini`, tests in `tests/`)
- `addopts = -v --strict-markers --tb=short`
- Markers: `unit`, `integration`, `slow`
- **`conftest.py` fixtures:**
  - `temp_dir` — workspace-local `.test_tmp/<uuid>/` directory, auto-cleaned after test
  - `sample_audio_path` — path string (file not created)
  - `sample_video_path` — path string (file not created)
  - `sample_transcript` — English sentence about AI
- **Monkeypatching pattern:** Tests patch at the module level (e.g. `monkeypatch.setattr(dubbing, "synthesize_khmer_tts", ...)`) not at the import level.
- Tests avoid actual downloads, Whisper loads, or API calls — all external I/O is mocked.
- Contract tests use `inspect.signature()` and `inspect.getdoc()` to validate function signatures and docstrings without execution.

---

### Coding Conventions (from `CLAUDE.md`)
- **Python 3.10+** with explicit type hints on all parameters and return types.
- `try/except` blocks for all network calls and file I/O.
- All API keys and config via `.env` / environment variables — never hardcoded.
- Concise docstrings on all core pipeline functions.
- Production-ready, modular architecture. No tutorial-style comments.
- Raise specific exceptions (`FileNotFoundError`, `RuntimeError`, `ValueError`, `EnvironmentError`) with descriptive messages.

---

### Pipeline Data Flow
```
URL
 └─► download_video_and_audio()
       ├─ video_path (MP4)
       └─ audio_path (WAV)
             └─► transcribe_audio()
                   ├─ language
                   ├─ transcript (str)
                   └─ segments [{id, start, end, text}, ...]
                         ├─► translate_to_khmer_script()        → khmer_script (str)
                         └─► translate_segments_to_khmer_subtitles() → segments [{id, start, end, text_km}]
                                    └─► generate_dubbed_video()
                                          ├─ synthesize_khmer_tts() → dubbed_audio.wav
                                          ├─ create_khmer_subtitle_file() → subtitles.srt
                                          └─ replace_video_audio() → dubbed_<uuid>.mp4
```

### Known Issues / Gotchas
- `audio_separator.py` is implemented but **not connected** to the main pipeline. Future integration point for background music preservation.
- FFmpeg subtitle path escaping uses POSIX format (`as_posix()`) with `\:` for Windows drive letters — required for `libass` filter.
- `generate_dubbed_video()` always returns `synthesized_audio_path` in the result even after cleanup (path still stored, file deleted).
- `voice_name`, `rate`, `volume`, and `pitch` in `synthesize_khmer_tts()` are retained for backward compatibility but are **no-ops** with VoxCPM2.
- VoxCPM2 requires `torch` and a GPU (or `VOXCPM_DEVICE=cpu`) — first call loads the model from HuggingFace; subsequent calls use the in-process singleton.
- `VOXCPM_AVAILABLE` is `False` when `voxcpm` or `soundfile` is not installed; `synthesize_khmer_tts` will raise `RuntimeError` wrapping an `ImportError` in that case.
- `max_output_tokens=2048` in Gemini calls may truncate very long subtitle batches — adjust `_chunk_subtitle_segments` batch size if needed.
- `secrets/` directory and `movie-491305-0b2ca8731dc8.json` (GCP service account) are gitignored but physically present in the project root.
