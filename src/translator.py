import os
from typing import Any, Dict

from google import genai
from google.genai import types

import re

def _chunk_text(text: str, max_chunk_size: int = 1500) -> list:
    """Split text into chunks intelligently, respecting paragraphs and sentences."""
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

def translate_to_khmer_script(transcript: str, source_lang: str = "auto") -> Dict[str, Any]:
    """Translate transcript into Khmer storytelling script using Google Gemini.

    Returns dict with keys: source_language, khmer_script, raw_response.
    """
    if not transcript or not transcript.strip():
        raise ValueError("Transcript cannot be empty")

    # Determine API key from environment
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        raise EnvironmentError("GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS is not set in environment")

    # Initialize Gemini client
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    # Split transcript into chunks intelligently
    transcript_chunks = _chunk_text(transcript, max_chunk_size=1500)
    
    khmer_chunks = []
    last_response = None

    try:
        # Use newer Gemini API with current model
        model_name = "gemini-2.5-pro"
        
        for i, chunk in enumerate(transcript_chunks):
            print(f"[TRANSLATOR] Translating chunk {i+1}/{len(transcript_chunks)}...")
            prompt_text = _build_khmer_hook_prompt(chunk.strip(), source_lang)
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            )
            
            output_text = response.text if hasattr(response, "text") else str(response)
            khmer_chunks.append(output_text.strip())
            last_response = response

        full_khmer_script = "\n\n".join(khmer_chunks)
        print(f"[TRANSLATOR] Total Khmer script length: {len(full_khmer_script)} chars")

        return {
            "source_language": source_lang,
            "khmer_script": full_khmer_script,
            "raw_response": last_response,
        }

    except Exception as exc:
        raise RuntimeError(f"Gemini translation step failed: {exc}") from exc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Translate transcript to Khmer storytelling script via Gemini")
    parser.add_argument("transcript", help="Whisper transcript text")
    parser.add_argument("--source-lang", default="auto", help="Detected source language, optional")
    args = parser.parse_args()

    result = translate_to_khmer_script(args.transcript, source_lang=args.source_lang)
    print(result["khmer_script"])
