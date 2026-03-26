import os
from typing import Any, Dict

import google.generativeai as genai


def _build_khmer_hook_prompt(transcript: str, source_lang: str) -> str:
    """Build prompt for Google Gemini to translate full transcript to Khmer with strict parity."""
    return (
        "Role: You are a professional, high-fidelity Khmer translator.\n"
        "Task: Perform a complete, literal translation of the provided transcript into Khmer.\n\n"
        "Strict Constraints:\n"
        "1. VERBATIM SCALE: Every sentence and idea must be translated. Do not summarize, truncate, or omit details.\n"
        "2. KEYWORD PRESERVATION: Keep technical terms or specific keywords in their original English form. Do not translate them.\n"
        "3. LINGUISTIC FLOW: Ensure the Khmer is natural but follows the pacing of the original source.\n"
        "4. FORMATTING: Output ONLY the Khmer text. Use paragraphs to reflect the original structure. No headers, no 'Here is the translation', no English notes.\n"
        "5. SYNTAX: Maintain the intensity and tone of the original speaker.\n\n"
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

    # API key should be in GOOGLE_APPLICATION_CREDENTIALS env var and authenticated by SDK
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        raise EnvironmentError("GOOGLE_APPLICATION_CREDENTIALS is not set in environment")

    # Initialize Gemini client once per process
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)

    # Split transcript into chunks of roughly 1000 characters to avoid summarization and handle length
    # Using sentences or newlines would be better, but for now simple split
    max_chunk_size = 1000
    transcript_chunks = [transcript[i:i+max_chunk_size] for i in range(0, len(transcript), max_chunk_size)]
    
    khmer_chunks = []
    last_response = None

    try:
        # Use newer Gemini API with current model
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        for i, chunk in enumerate(transcript_chunks):
            print(f"[TRANSLATOR] Translating chunk {i+1}/{len(transcript_chunks)}...")
            prompt_text = _build_khmer_hook_prompt(chunk.strip(), source_lang)
            
            response = model.generate_content(
                prompt_text,
                generation_config=genai.types.GenerationConfig(
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
