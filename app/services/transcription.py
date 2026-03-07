import os
import json
import argparse
from openai import OpenAI
from app.core.config import settings


def transcribe_audio(file_path: str, api_key: str) -> dict:
    """Transcribe an audio file using the Pollinations Scribe model.

    Sends the audio file to the Pollinations-hosted Scribe (ElevenLabs
    Scribe v2) model via the OpenAI-compatible API. Returns a normalized
    dict with full text and segment-level timestamps. Results are cached
    to disk to avoid redundant API calls.

    Args:
        file_path: Absolute or relative path to the audio file.
        api_key: Pollinations API key for authentication.

    Returns:
        A dict with shape ``{text: str, segments: [{start, end, text}]}``.

    Raises:
        openai.APIError: If the transcription API call fails.
    """
    # Check for cached transcription
    cache_path = f"{file_path}.json"
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass  # corrupted cache, proceed to re-transcribe

    client = OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=api_key,
    )

    with open(file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), file.read()),
            model="scribe",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language="en",
            temperature=0.0,
        )

    # Convert response object to dict for serialisation
    data = transcription.model_dump()

    # Persist the full raw response (includes words array for subtitles)
    raw_path = cache_path.replace(".json", "_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    # Build the normalised cache with only the fields consumers need
    result = {
        "text": data["text"],
        "segments": [
            {
                "start": s["start"],
                "end": s["end"],
                "text": s["text"],
            }
            for s in data["segments"]
        ],
    }

    # Save normalised result to cache
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=4)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file via Pollinations Scribe."
    )
    parser.add_argument("file", nargs="?", default="audio.mp3")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("POLLINATIONS_API_KEY", "dummy_key_for_test"),
        help="Pollinations API key (default: $POLLINATIONS_API_KEY)",
    )
    args = parser.parse_args()

    try:
        res = transcribe_audio(args.file, api_key=args.api_key)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")