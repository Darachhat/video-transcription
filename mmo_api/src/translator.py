import ast
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from app.core.config.config import settings

# NVIDIA API Configuration
DEFAULT_NVIDIA_MODELS = ("meta/llama-3.1-70b-instruct", "meta/llama-3.3-70b-instruct")

# Max attempts per model when the error is a rate-limit (1 initial + 1 wait-and-retry).
_MAX_QUOTA_RETRIES_PER_MODEL = settings.MAX_QUOTA_RETRIES

def _chunk_text(text: str, max_chunk_size: int = None) -> list:
    """Split text into chunks intelligently, respecting paragraphs and sentences."""
    if max_chunk_size is None:
        max_chunk_size = settings.TRANSCRIPT_CHUNK_SIZE
    if not text:
        return []

    # First split by paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_chunk_paragraphs = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # If adding this paragraph exceeds limit, finalize current chunk
        if current_length + len(paragraph) > max_chunk_size and current_chunk_paragraphs:
            chunks.append("\n\n".join(current_chunk_paragraphs))
            current_chunk_paragraphs = []
            current_length = 0

        # If a single paragraph is larger than the chunk size, split by sentences
        if len(paragraph) > max_chunk_size:
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            current_paragraph_sentences = []
            temp_len = 0

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # If adding this sentence to the current paragraph portion exceeds limit
                if temp_len + len(sentence) > max_chunk_size and current_paragraph_sentences:
                    # Finalize the current paragraph portion as a chunk
                    chunks.append(" ".join(current_paragraph_sentences))
                    current_paragraph_sentences = []
                    temp_len = 0

                current_paragraph_sentences.append(sentence)
                temp_len += len(sentence) + 1 # +1 for space

            if current_paragraph_sentences:
                current_chunk_paragraphs.append(" ".join(current_paragraph_sentences))
                current_length += temp_len + 2 # +2 for potential newlines
        else:
            current_chunk_paragraphs.append(paragraph)
            current_length += len(paragraph) + 2

    if current_chunk_paragraphs:
        chunks.append("\n\n".join(current_chunk_paragraphs))

    return chunks

def _build_khmer_hook_prompt(transcript: str, source_lang: str) -> str:
    """Build prompt for Google Gemini to translate full transcript to Khmer with strict parity."""
    return (
        "Role: You are an expert, high-fidelity native Khmer translator and linguist with deep understanding of cultural nuances.\n"
        "Task: Perform a complete, highly accurate translation of the provided transcript into natural-sounding Khmer.\n\n"
        "Strict Constraints:\n"
        "1. NO SUMMARIZATION: Every single sentence, clause, and idea MUST be translated. Do NOT summarize, truncate, or omit ANY details. Maintain exact parity with the source length.\n"
        "2. ACCURACY & TONE: The translation must perfectly reflect the original tone (e.g., formal, conversational, excited, somber) and accurately convey all facts, numbers, and nuances.\n"
        "3. LINGUISTIC FLOW: Ensure the Khmer syntax is completely natural and grammatically correct for a native speaker, avoiding awkward literal translations while preserving the original meaning.\n"
        "4. KEYWORD PRESERVATION: Keep technical terms, brand names, or specific keywords in their original English form if there is no widely accepted Khmer equivalent. Do not forcefully translate them.\n"
        "5. FORMATTING: Output ONLY the Khmer text. Strictly maintain the paragraph structure of the original transcript. Do not add headers, bullet points, 'Here is the translation', or any English notes.\n\n"
        f"Original Transcript (Source: {source_lang}):\n"
        "--- START ---\n"
        f"{transcript}\n"
        "--- END ---\n\n"
        "Khmer Translation:"
    )

def _build_subtitle_translation_prompt(segments: List[Dict[str, Any]], source_lang: str) -> str:
    """Build prompt for translating timed transcript segments into Khmer subtitle lines."""
    subtitle_payload = json.dumps(
        [{"id": segment["id"], "text": segment["text"]} for segment in segments],
        ensure_ascii=False,
        indent=2,
    )
    return (
        "Role: You are an expert native Khmer subtitle translator.\n"
        "Task: Translate each subtitle segment into natural Khmer suitable for on-screen captions.\n\n"
        "Strict Constraints:\n"
        "1. Return ONLY valid JSON. Do not wrap it in markdown.\n"
        "2. Keep the exact same number of items and the exact same ids.\n"
        "3. Do not merge, split, omit, or reorder segments.\n"
        "4. Each returned item must contain only two keys: id and text.\n"
        "5. Translate each text value into concise, natural Khmer while preserving names, numbers, and meaning.\n"
        "6. Keep technical terms or brand names in English when there is no natural Khmer equivalent.\n\n"
        f"Source language: {source_lang}\n"
        "Subtitle segments JSON:\n"
        f"{subtitle_payload}\n\n"
        "Return JSON array:"
    )

def _build_subtitle_repair_prompt(
    segments: List[Dict[str, Any]],
    invalid_response: str,
    source_lang: str,
) -> str:
    """Build prompt to repair a malformed subtitle translation into valid JSON."""
    subtitle_payload = json.dumps(
        [{"id": segment["id"], "text": segment["text"]} for segment in segments],
        ensure_ascii=False,
        indent=2,
    )
    return (
        "The previous subtitle translation response was malformed.\n"
        "Rewrite it as valid JSON only.\n\n"
        "Rules:\n"
        "1. Return ONLY a JSON array.\n"
        "2. Keep the same number of items and the same ids.\n"
        "3. Each item must contain only id and text.\n"
        "4. Each text value must be natural Khmer subtitle text.\n"
        "5. Do not add markdown, comments, or explanations.\n\n"
        f"Source language: {source_lang}\n"
        "Original subtitle segments:\n"
        f"{subtitle_payload}\n\n"
        "Malformed response to repair:\n"
        f"{invalid_response}\n\n"
        "Return repaired JSON array:"
    )

def _build_single_subtitle_translation_prompt(text: str, source_lang: str) -> str:
    """Build prompt for translating a single subtitle line."""
    return (
        "Role: You are an expert native Khmer subtitle translator.\n"
        "Task: Translate the following subtitle line into concise, natural Khmer.\n\n"
        "Strict Constraints:\n"
        "1. Output ONLY the Khmer subtitle text.\n"
        "2. Do not add quotes, markdown, labels, or explanations.\n"
        "3. Preserve names, numbers, and technical terms when needed.\n\n"
        f"Source language: {source_lang}\n"
        f"Subtitle: {text}\n\n"
        "Khmer subtitle:"
    )

def _get_api_key() -> Optional[str]:
    """Get NVIDIA API key from environment."""
    return os.getenv("NVIDIA_API_KEY")

def _ensure_nvidia_credentials() -> None:
    """Ensure NVIDIA API credentials are configured."""
    api_key = _get_api_key()
    if not api_key:
        raise EnvironmentError(
            "NVIDIA API credentials are not configured. Set NVIDIA_API_KEY environment variable."
        )

def _get_configured_models() -> List[str]:
    """Get configured NVIDIA models from environment."""
    raw_models = os.getenv("NVIDIA_MODELS")
    if raw_models:
        models = [model.strip() for model in raw_models.split(",") if model.strip()]
        if models:
            return models

    single_model = os.getenv("NVIDIA_MODEL")
    if single_model and single_model.strip():
        return [single_model.strip()]

    return list(DEFAULT_NVIDIA_MODELS)

def _normalize_error_text(exc: Exception) -> str:
    """Normalize error text for comparison."""
    return " ".join(str(exc).split())

def _extract_retry_delay_seconds(error_text: str) -> Optional[int]:
    """Extract retry delay from error text."""
    retry_match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", error_text, re.IGNORECASE)
    if retry_match:
        return max(1, round(float(retry_match.group(1))))

    retry_match = re.search(r"retry.after.?([0-9]+)", error_text, re.IGNORECASE)
    if retry_match:
        return int(retry_match.group(1))

    return None

def _is_quota_error(exc: Exception) -> bool:
    """Check if error is a quota/rate limit error."""
    error_text = _normalize_error_text(exc).lower()
    return any(
        marker in error_text
        for marker in ("quota exceeded", "rate limit exceeded", "too many requests", "429", "resource_exhausted")
    )

def _is_server_overload_error(exc: Exception) -> bool:
    """Check if error is a transient server overload error."""
    error_text = _normalize_error_text(exc).lower()
    return any(
        marker in error_text
        for marker in ("503", "unavailable", "server error", "temporarily", "overloaded", "500", "502")
    )

def _is_timeout_error(exc: Exception) -> bool:
    """Check if error is a timeout error (transient network issue)."""
    error_text = _normalize_error_text(exc).lower()
    return any(
        marker in error_text
        for marker in ("timeout", "timed out", "connection reset", "connection refused", "read timed out")
    )

def _should_try_next_model(exc: Exception) -> bool:
    """Check if we should try the next model on this error."""
    if _is_quota_error(exc):
        return True
    if _is_server_overload_error(exc):
        return True
    if _is_timeout_error(exc):
        return True

    error_text = _normalize_error_text(exc).lower()
    return any(
        marker in error_text
        for marker in ("404", "not found", "not supported", "permission denied", "invalid model")
    )

def _call_nvidia_api(model_name: str, prompt_text: str) -> str:
    """Call NVIDIA API using OpenAI-compatible client."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("NVIDIA API key not configured")

    client = OpenAI(
        base_url=settings.NVIDIA_API_BASE,
        api_key=api_key,
        timeout=settings.NVIDIA_API_TIMEOUT,
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt_text}
            ],
            temperature=settings.NVIDIA_TEMPERATURE,
            max_tokens=settings.NVIDIA_MAX_TOKENS,
        )
        
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            return content.strip()
        
        raise RuntimeError(f"Unexpected NVIDIA API response: no choices in response")
    
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            raise RuntimeError(f"Rate limit exceeded: {error_msg}") from e
        elif "500" in error_msg or "502" in error_msg or "503" in error_msg or "overloaded" in error_msg.lower():
            raise RuntimeError(f"Server error: {error_msg}") from e
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            raise RuntimeError("NVIDIA API request timed out") from e
        else:
            raise RuntimeError(f"NVIDIA API request failed: {error_msg}") from e

def _extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text.strip()
    return str(response).strip()

def _translate_with_model_fallback(
    model_names: List[str],
    prompt_text: str,
    request_label: str,
) -> Tuple[str, str]:
    """Generate content with model fallbacks and quota-aware retry.

    For each model in ``model_names``:
    - On a quota/rate-limit error: waits for the API-suggested delay (or 30 s)
      and retries the **same** model once before moving on to the next.
    - On a timeout/overload error: waits with exponential backoff then retries.
    - On a 404 / permission / unknown error: skips to the next model immediately.
    - On any other error: stops and raises.
    """
    last_error = None

    for model_idx, model_name in enumerate(model_names):
        is_last_model = model_idx == len(model_names) - 1

        for attempt in range(settings.MAX_QUOTA_RETRIES):
            try:
                output_text = _call_nvidia_api(model_name, prompt_text)
                if not output_text:
                    raise RuntimeError(f"Model {model_name} returned an empty translation")
                return output_text, model_name

            except Exception as exc:
                last_error = exc
                is_last_attempt = attempt >= settings.MAX_QUOTA_RETRIES - 1

                is_quota = _is_quota_error(exc)
                is_overload = _is_server_overload_error(exc)
                is_timeout = _is_timeout_error(exc)

                if is_quota or is_overload or is_timeout:
                    if is_last_model and not is_last_attempt:
                        # No fallback model left — wait and retry the same one.
                        if is_quota:
                            suggested = _extract_retry_delay_seconds(_normalize_error_text(exc))
                            delay = suggested or 30
                            kind = "quota"
                        elif is_overload:
                            delay = 10
                            kind = "503 overload"
                        else:  # is_timeout
                            # Exponential backoff for timeouts
                            delay = min(5 * (2 ** attempt), 60)  # 5s, 10s, 20s, up to 60s
                            kind = "timeout"
                        
                        print(
                            f"[TRANSLATOR] Model {model_name} {kind} for {request_label}; "
                            f"no fallback models left — waiting {delay}s then retrying "
                            f"({attempt + 2}/{settings.MAX_QUOTA_RETRIES})..."
                        )
                        time.sleep(delay)
                        continue  # retry same model

                    # Another model is available (or retries exhausted): fall through.
                    if not is_last_model:
                        if is_quota:
                            kind = "quota hit"
                        elif is_overload:
                            kind = "503 overload"
                        else:
                            kind = "timeout"
                        print(
                            f"[TRANSLATOR] Model {model_name} {kind} for "
                            f"{request_label}; trying next model..."
                        )
                    break

                if _should_try_next_model(exc):
                    if not is_last_model:
                        print(
                            f"[TRANSLATOR] Model {model_name} failed for {request_label}; "
                            "trying next configured model..."
                        )
                    break  # move to next model in outer loop

                # Non-retriable error — surface immediately.
                break

    assert last_error is not None
    raise RuntimeError(_build_translation_failure(model_names, last_error)) from last_error

def _strip_markdown_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()

def _extract_json_payload(text: str) -> str:
    """Extract JSON payload from model response."""
    cleaned = _strip_markdown_code_fences(text)
    if not cleaned:
        raise RuntimeError("NVIDIA translation returned empty content")

    payload_candidates: List[str] = [cleaned]

    array_match = re.search(r"(\[[\s\S]*\])", cleaned)
    if array_match:
        payload_candidates.append(array_match.group(1))

    object_match = re.search(r"(\{[\s\S]*\})", cleaned)
    if object_match:
        payload_candidates.append(object_match.group(1))

    for candidate in payload_candidates:
        stripped = candidate.strip()
        if (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("{") and stripped.endswith("}")
        ):
            return stripped

    raise RuntimeError("NVIDIA translation returned invalid JSON")

def _load_structured_payload(payload_text: str) -> Any:
    """Parse JSON-like payloads with a tolerant fallback."""
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(payload_text)
        except (SyntaxError, ValueError) as exc:
            raise RuntimeError(f"Translation returned invalid JSON: {exc}") from exc

def _normalise_subtitle_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalised_segments: List[Dict[str, Any]] = []

    for index, segment in enumerate(segments):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        normalised_segments.append(
            {
                "id": segment.get("id", index),
                "start": start,
                "end": max(end, start),
                "text": text,
            }
        )

    return normalised_segments

def _chunk_subtitle_segments(
    segments: List[Dict[str, Any]],
    max_chunk_size: int = None,
) -> List[List[Dict[str, Any]]]:
    """Chunk subtitle segments into batches."""
    if max_chunk_size is None:
        max_chunk_size = settings.SUBTITLE_BATCH_CHUNK_SIZE
    batches: List[List[Dict[str, Any]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_size = 0

    for segment in segments:
        estimated_size = len(str(segment["id"])) + len(segment["text"]) + 32
        if current_batch and current_size + estimated_size > max_chunk_size:
            batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append(segment)
        current_size += estimated_size

    if current_batch:
        batches.append(current_batch)

    return batches

def _parse_subtitle_translation_response(
    response_text: str,
    source_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    try:
        payload = _load_structured_payload(_extract_json_payload(response_text))
    except RuntimeError:
        raise

    if isinstance(payload, dict):
        for key in ("segments", "subtitles", "items", "translations", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break

    if not isinstance(payload, list):
        raise RuntimeError("Translation did not return a JSON array")
    if len(payload) != len(source_segments):
        raise RuntimeError(
            "Translation returned the wrong number of segments "
            f"(expected {len(source_segments)}, got {len(payload)})"
        )

    translated_by_id: Dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError("Translation returned a non-object segment")
        if "id" not in item or "text" not in item:
            raise RuntimeError("Translation returned a segment without id/text")

        translated_text = str(item["text"]).strip()
        if not translated_text:
            raise RuntimeError(f"Translation returned an empty subtitle for id={item['id']}")
        translated_by_id[str(item["id"])] = translated_text

    translated_segments: List[Dict[str, Any]] = []
    for source_segment in source_segments:
        segment_key = str(source_segment["id"])
        if segment_key not in translated_by_id:
            raise RuntimeError(f"Translation omitted subtitle id={source_segment['id']}")

        translated_segments.append(
            {
                "id": source_segment["id"],
                "start": source_segment["start"],
                "end": source_segment["end"],
                "text": translated_by_id[segment_key],
            }
        )

    return translated_segments

def _repair_subtitle_translation_batch(
    model_names: List[str],
    source_lang: str,
    source_segments: List[Dict[str, Any]],
    invalid_response: str,
) -> Tuple[List[Dict[str, Any]], str]:
    """Attempt to repair malformed subtitle JSON using the model."""
    repair_prompt = _build_subtitle_repair_prompt(source_segments, invalid_response, source_lang)
    repaired_text, repair_model_name = _translate_with_model_fallback(
        model_names=model_names,
        prompt_text=repair_prompt,
        request_label="subtitle JSON repair",
    )
    repaired_segments = _parse_subtitle_translation_response(repaired_text, source_segments)
    return repaired_segments, repair_model_name

def _translate_subtitle_segments_line_by_line(
    model_names: List[str],
    source_lang: str,
    source_segments: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Fallback translator that translates subtitle segments one at a time."""
    translated_segments: List[Dict[str, Any]] = []
    models_used: List[str] = []

    for segment in source_segments:
        prompt_text = _build_single_subtitle_translation_prompt(segment["text"], source_lang)
        translated_text, model_name = _translate_with_model_fallback(
            model_names=model_names,
            prompt_text=prompt_text,
            request_label=f"subtitle line {segment['id']}",
        )
        translated_segments.append(
            {
                "id": segment["id"],
                "start": segment["start"],
                "end": segment["end"],
                "text": _strip_markdown_code_fences(translated_text).strip().strip('"').strip("'"),
            }
        )
        models_used.append(model_name)

    return translated_segments, models_used

def _build_translation_failure(model_names: List[str], exc: Exception) -> str:
    """Build error message for translation failure."""
    error_text = _normalize_error_text(exc)
    model_list = ", ".join(model_names)

    if _is_quota_error(exc):
        return (
            f"NVIDIA translation failed due to quota exhaustion after trying all models: {model_list}. "
            f"Last error: {error_text}."
            f" To add more fallback models set NVIDIA_MODELS in .env, e.g.: "
            f"NVIDIA_MODELS=nvidia/llama2-70b-chat,meta/llama2-70b-chat-hf"
        )

    if _is_server_overload_error(exc):
        return (
            f"NVIDIA API is temporarily overloaded after trying all models: {model_list}. "
            f"Last error: {error_text}."
            f" This is a transient issue. Please retry the job in a minute."
        )

    if _is_timeout_error(exc):
        return (
            f"NVIDIA translation timed out after trying all models: {model_list}. "
            f"Last error: {error_text}. "
            f"The API is responding slowly or the content is complex. "
            f"This is a transient issue. Please retry the job in a minute. "
            f"If the issue persists, you can increase NVIDIA_API_TIMEOUT in .env (current: {os.getenv('NVIDIA_API_TIMEOUT', '120')}s)."
        )

    return f"NVIDIA translation step failed after trying models: {model_list}. Last error: {error_text}"

def translate_to_khmer_script(transcript: str, source_lang: str = "auto") -> Dict[str, Any]:
    """Translate transcript into Khmer storytelling script using NVIDIA LLM.

    Returns dict with keys: source_language, khmer_script, models_used.
    """
    if not transcript or not transcript.strip():
        raise ValueError("Transcript cannot be empty")

    _ensure_nvidia_credentials()

    # Split transcript into chunks intelligently
    transcript_chunks = _chunk_text(transcript)

    model_names = _get_configured_models()
    khmer_chunks = []
    models_used = []

    try:
        for i, chunk in enumerate(transcript_chunks):
            print(f"[TRANSLATOR] Translating chunk {i+1}/{len(transcript_chunks)}...")
            prompt_text = _build_khmer_hook_prompt(chunk.strip(), source_lang)
            output_text, model_name = _translate_with_model_fallback(
                model_names=model_names,
                prompt_text=prompt_text,
                request_label=f"chunk {i+1}",
            )
            khmer_chunks.append(output_text)
            models_used.append(model_name)

        full_khmer_script = "\n\n".join(khmer_chunks)
        print(f"[TRANSLATOR] Total Khmer script length: {len(full_khmer_script)} chars")

        return {
            "source_language": source_lang,
            "khmer_script": full_khmer_script,
            "raw_response": None,
            "models_used": models_used,
        }

    except Exception as exc:
        if isinstance(exc, RuntimeError) and str(exc).startswith("NVIDIA translation"):
            raise
        raise RuntimeError(f"NVIDIA translation step failed: {_normalize_error_text(exc)}") from exc

def translate_segments_to_khmer_subtitles(
    segments: List[Dict[str, Any]],
    source_lang: str = "auto",
) -> Dict[str, Any]:
    """Translate timed transcript segments into Khmer subtitle segments.

    Returns dict with keys: source_language, segments, raw_response, models_used.
    """
    normalised_segments = _normalise_subtitle_segments(segments)
    if not normalised_segments:
        return {
            "source_language": source_lang,
            "segments": [],
            "raw_response": None,
            "models_used": [],
        }

    _ensure_nvidia_credentials()

    batched_segments = _chunk_subtitle_segments(normalised_segments)
    model_names = _get_configured_models()
    translated_segments: List[Dict[str, Any]] = []
    models_used: List[str] = []

    try:
        for index, batch in enumerate(batched_segments):
            print(f"[TRANSLATOR] Translating subtitle batch {index+1}/{len(batched_segments)}...")
            prompt_text = _build_subtitle_translation_prompt(batch, source_lang)
            output_text, model_name = _translate_with_model_fallback(
                model_names=model_names,
                prompt_text=prompt_text,
                request_label=f"subtitle batch {index+1}",
            )
            try:
                parsed_segments = _parse_subtitle_translation_response(output_text, batch)
                translated_segments.extend(parsed_segments)
                models_used.append(model_name)
                continue
            except RuntimeError as exc:
                print(
                    f"[TRANSLATOR] Subtitle batch {index+1} returned malformed JSON; "
                    "attempting repair..."
                )
                repair_error = exc

            try:
                repaired_segments, repair_model_name = _repair_subtitle_translation_batch(
                    model_names=model_names,
                    source_lang=source_lang,
                    source_segments=batch,
                    invalid_response=output_text,
                )
                translated_segments.extend(repaired_segments)
                models_used.extend([model_name, repair_model_name])
                continue
            except RuntimeError:
                print(
                    f"[TRANSLATOR] Subtitle batch {index+1} repair failed; "
                    "falling back to line-by-line subtitle translation..."
                )

            line_segments, line_models = _translate_subtitle_segments_line_by_line(
                model_names=model_names,
                source_lang=source_lang,
                source_segments=batch,
            )
            if not line_segments:
                raise repair_error
            translated_segments.extend(line_segments)
            models_used.extend(line_models)

        return {
            "source_language": source_lang,
            "segments": translated_segments,
            "raw_response": None,
            "models_used": models_used,
        }

    except Exception as exc:
        if isinstance(exc, RuntimeError) and str(exc).startswith("NVIDIA translation"):
            raise
        raise RuntimeError(f"NVIDIA subtitle translation failed: {_normalize_error_text(exc)}") from exc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Translate transcript to Khmer storytelling script via NVIDIA LLM")
    parser.add_argument("transcript", help="Whisper transcript text")
    parser.add_argument("--source-lang", default="auto", help="Detected source language, optional")
    args = parser.parse_args()

    result = translate_to_khmer_script(args.transcript, source_lang=args.source_lang)
    print(result["khmer_script"])
