# NVIDIA API Setup Guide

This project has been migrated from Google Gemini API to NVIDIA API for translation services.

## Quick Start

### 1. Get NVIDIA API Key

1. Visit [NVIDIA Build API Catalog](https://build.nvidia.com/models)
2. Sign up / Login to your NVIDIA account
3. Browse available models (e.g., Meta Llama 2 70B Chat)
4. Generate an API key in your account settings
5. Copy the API key

### 2. Configure Environment Variables

Create a `.env` file in the `mmo_api` directory (or update your existing one):

```bash
# NVIDIA API Configuration
NVIDIA_API_KEY=your-api-key-here

# Optional: Specify primary model (defaults to nvidia/llama2-70b-chat)
NVIDIA_MODEL=nvidia/llama2-70b-chat

# Optional: Fallback models (comma-separated)
# NVIDIA_MODELS=nvidia/llama2-70b-chat,meta/llama2-70b-chat-hf
```

### 3. Update Dependencies

```bash
cd mmo_api
pip install -r requirements.txt
```

This will remove Google Gemini SDKs and keep the `requests` library for API calls.

## Configuration Details

### Available Models

The translator supports any model available through NVIDIA's API Catalog:

- `nvidia/llama2-70b-chat` (default)
- `meta/llama2-70b-chat-hf`
- Other models available in the catalog

### Environment Variables Reference

| Variable         | Required | Description                                      |
| ---------------- | -------- | ------------------------------------------------ |
| `NVIDIA_API_KEY` | Yes      | Your NVIDIA API key from build.nvidia.com        |
| `NVIDIA_MODEL`   | No       | Primary translation model (defaults shown below) |
| `NVIDIA_MODELS`  | No       | Comma-separated list of fallback models          |

#### Default Models

If not specified, the translator uses:

1. `nvidia/llama2-70b-chat`
2. `meta/llama2-70b-chat-hf`

### API Endpoint

- **Base URL**: `https://integrate.api.nvidia.com/v1`
- **Endpoint**: `/chat/completions` (OpenAI-compatible API)
- **Auth**: Bearer token in `Authorization` header

## Error Handling

The translator implements smart fallback logic:

- **Rate Limits (429)**: Automatically waits and retries
- **Server Overload (503)**: Retries with exponential backoff
- **Model Not Found**: Tries next model in the fallback list
- **Quota Exhaustion**: Falls back to next model or line-by-line translation

## Troubleshooting

### "NVIDIA API credentials are not configured"

- Ensure `NVIDIA_API_KEY` is set in your `.env` file
- Check that the key is valid and hasn't expired

### "Rate limit exceeded"

- NVIDIA API has rate limits - wait a moment and retry
- Consider using fallback models via `NVIDIA_MODELS` env var

### "Model not supported"

- Check that the model name is correct (use models from catalog)
- Verify the model is available in your account tier

### Timeout or Connection Errors

- Check your internet connection
- Verify the NVIDIA API endpoint is accessible
- Check for firewall/proxy issues

## Migration Notes

This project was previously using Google Gemini API. Key changes:

1. **Removed dependencies**: `google-genai`, `google-generativeai`
2. **Environment variables**: Changed from `GOOGLE_API_KEY`/`GEMINI_API_KEY` to `NVIDIA_API_KEY`
3. **Model configuration**: Changed from `GEMINI_MODELS` to `NVIDIA_MODELS`
4. **API calls**: Now uses HTTP requests via `requests` library
5. **Error messages**: Updated to reference NVIDIA instead of Gemini

## Example Usage

```python
from src.translator import translate_segments_to_khmer_subtitles

segments = [
    {"id": 0, "start": 0.0, "end": 2.5, "text": "Hello, world!"},
    {"id": 1, "start": 2.5, "end": 5.0, "text": "This is a test."}
]

result = translate_segments_to_khmer_subtitles(segments, source_lang="en")
print(result)
```

## Support

For NVIDIA API support, visit:

- [NVIDIA Build Documentation](https://docs.nvidia.com/ai-enterprise/on-demand/user-guide-nvidia-api-for-open-models.html)
- [API Catalog](https://build.nvidia.com/models)
