"""
Phase 0 Blocking Gate: Pollinations Transcription API Schema Verification

Verifies that Pollinations /v1/audio/transcriptions returns a schema
compatible with the existing SubtitleService pipeline.

Expected schema (from Groq Whisper verbose_json):
    {
        "words": [{"word": str, "start": float, "end": float}, ...],
        "segments": [{"start": float, "end": float, "text": str}, ...],
        "text": str,
        ...
    }

SubtitleService hard dependency (subtitle_service.py line 11):
    data.get("words", [])  ->  SubtitleWord(word=str, start=float, end=float)
"""

import json
import math
import os
import struct
import sys
import wave
from typing import Any

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get(
    "LLM_API_KEY", "sk_5zBErRz0J7imiRSjDtAf0c4HzAFcH7Kx"
)
BASE_URL = "https://gen.pollinations.ai/v1"
TEST_AUDIO_PATH = os.path.join(
    os.path.dirname(__file__), "_test_speech.wav"
)

# Models to test — whisper-large-v3 (standard) and scribe (ElevenLabs)
MODELS_TO_TEST = ["whisper-large-v3", "scribe"]

# Schema the codebase expects (from transcription.py + subtitle_service.py)
EXPECTED_WORD_KEYS = {"word", "start", "end"}
EXPECTED_SEGMENT_KEYS = {"start", "end", "text"}


# ---------------------------------------------------------------------------
# Test audio generation
# ---------------------------------------------------------------------------
def generate_test_wav(filepath: str, duration_s: float = 3.0) -> str:
    """Generate a WAV file with a dual-tone signal that mimics speech cadence.

    Uses two frequencies with amplitude modulation to produce a signal
    that speech-detection models are more likely to process (pure sine
    waves are sometimes ignored by Whisper as non-speech).

    Args:
        filepath: Output WAV path.
        duration_s: Duration in seconds.

    Returns:
        The filepath written.
    """
    sample_rate = 16000
    n_samples = int(sample_rate * duration_s)

    # Two tones with amplitude modulation to simulate formant-like energy
    freq_1 = 300   # Approximate F1 of a vowel
    freq_2 = 2500  # Approximate F2 of a vowel
    mod_freq = 4   # Syllable-rate modulation (~4 Hz)

    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # Amplitude envelope (syllable-rate)
        envelope = 0.5 + 0.5 * math.sin(2 * math.pi * mod_freq * t)
        # Mix of two formant-like tones
        sample = envelope * (
            0.6 * math.sin(2 * math.pi * freq_1 * t)
            + 0.4 * math.sin(2 * math.pi * freq_2 * t)
        )
        # Scale to 16-bit PCM range
        samples.append(int(sample * 32000))

    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    print(f"[INFO] Generated test WAV: {filepath} "
          f"({duration_s}s, {sample_rate}Hz, mono)")
    return filepath


# ---------------------------------------------------------------------------
# API call helpers
# ---------------------------------------------------------------------------
def call_transcription(
    filepath: str,
    model: str = "whisper-large-v3",
    verbose: bool = True,
    granularities: bool = True,
) -> dict[str, Any] | None:
    """Call Pollinations transcription endpoint via OpenAI SDK.

    Args:
        filepath: Path to audio file.
        model: Model name to use.
        verbose: Whether to request verbose_json format.
        granularities: Whether to request word+segment granularities.

    Returns:
        The response as a dict, or None on failure.
    """
    from openai import OpenAI

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    file_handle = open(filepath, "rb")
    kwargs: dict[str, Any] = {
        "model": model,
        "file": file_handle,
        "language": "en",
        "temperature": 0.0,
    }
    if verbose:
        kwargs["response_format"] = "verbose_json"
    if granularities:
        kwargs["timestamp_granularities"] = ["word", "segment"]

    label = (
        f"model={model}, verbose_json={verbose}, "
        f"timestamp_granularities={granularities}"
    )
    print(f"\n{'='*70}")
    print(f"[CALL] Transcription request")
    print(f"  {label}")
    print(f"{'='*70}")

    try:
        result = client.audio.transcriptions.create(**kwargs)

        # Extract dict from response
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = result
        else:
            # Some SDK versions return a plain object; try __dict__
            data = result.__dict__

        return data

    except Exception as exc:
        print(f"[ERROR] API call failed: {type(exc).__name__}: {exc}")
        return None
    finally:
        file_handle.close()


# ---------------------------------------------------------------------------
# Schema verification
# ---------------------------------------------------------------------------
def check_words_array(data: dict[str, Any]) -> list[str]:
    """Verify the words array matches SubtitleService expectations.

    Returns:
        List of failure messages (empty = pass).
    """
    failures: list[str] = []

    if "words" not in data:
        failures.append("MISSING top-level 'words' key")
        return failures

    words = data["words"]
    if not isinstance(words, list):
        failures.append(
            f"'words' is {type(words).__name__}, expected list"
        )
        return failures

    if len(words) == 0:
        failures.append(
            "'words' array is EMPTY (no word-level timestamps returned)"
        )
        return failures

    print(f"  words count: {len(words)}")
    print(f"  first word sample: {json.dumps(words[0], indent=4)}")
    if len(words) > 1:
        print(f"  second word sample: {json.dumps(words[1], indent=4)}")

    first = words[0]
    actual_keys = set(first.keys())
    missing = EXPECTED_WORD_KEYS - actual_keys
    extra = actual_keys - EXPECTED_WORD_KEYS

    if missing:
        failures.append(
            f"words[0] MISSING keys: {missing}  (has: {actual_keys})"
        )

        # Check for alternative key names that need mapping
        alt_mappings = []
        if "word" not in actual_keys:
            # Check for common alternatives
            for alt in ["text", "value", "content", "w", "punctuated_word"]:
                if alt in actual_keys:
                    alt_mappings.append(f"  -> '{alt}' could map to 'word'")
        if "start" not in actual_keys:
            for alt in ["start_time", "startTime", "begin", "from"]:
                if alt in actual_keys:
                    alt_mappings.append(
                        f"  -> '{alt}' could map to 'start'"
                    )
        if "end" not in actual_keys:
            for alt in ["end_time", "endTime", "finish", "to"]:
                if alt in actual_keys:
                    alt_mappings.append(f"  -> '{alt}' could map to 'end'")

        if alt_mappings:
            failures.append(
                "MAPPING SUGGESTIONS:\n" + "\n".join(alt_mappings)
            )

    if extra:
        print(f"  [INFO] words[0] has extra keys: {extra}")

    # Type checks on expected keys that are present
    for key in EXPECTED_WORD_KEYS & actual_keys:
        val = first[key]
        if key == "word":
            if not isinstance(val, str):
                failures.append(
                    f"words[0].word is {type(val).__name__}, expected str"
                )
        else:
            if not isinstance(val, (int, float)):
                failures.append(
                    f"words[0].{key} is {type(val).__name__}, "
                    f"expected float/int"
                )

    # Check timestamp units -- Groq returns seconds (< 100 for short audio)
    if (
        "start" in actual_keys
        and isinstance(first.get("start"), (int, float))
    ):
        if first["start"] > 100:
            failures.append(
                f"words[0].start={first['start']} -- "
                f"looks like MILLISECONDS, expected SECONDS"
            )

    return failures


def check_segments_array(data: dict[str, Any]) -> list[str]:
    """Verify the segments array matches transcription.py expectations.

    Returns:
        List of failure messages (empty = pass).
    """
    failures: list[str] = []

    if "segments" not in data:
        failures.append("MISSING top-level 'segments' key")
        return failures

    segments = data["segments"]
    if not isinstance(segments, list):
        failures.append(
            f"'segments' is {type(segments).__name__}, expected list"
        )
        return failures

    if len(segments) == 0:
        failures.append("'segments' array is EMPTY")
        return failures

    print(f"  segments count: {len(segments)}")
    print(f"  first segment sample: {json.dumps(segments[0], indent=4)}")

    first = segments[0]
    actual_keys = set(first.keys())
    missing = EXPECTED_SEGMENT_KEYS - actual_keys
    extra = actual_keys - EXPECTED_SEGMENT_KEYS

    if missing:
        failures.append(
            f"segments[0] MISSING keys: {missing}  (has: {actual_keys})"
        )
    if extra:
        print(f"  [INFO] segments[0] has extra keys: {extra}")

    # Type checks
    for key in EXPECTED_SEGMENT_KEYS & actual_keys:
        val = first[key]
        if key == "text":
            if not isinstance(val, str):
                failures.append(
                    f"segments[0].text is {type(val).__name__}, "
                    f"expected str"
                )
        else:
            if not isinstance(val, (int, float)):
                failures.append(
                    f"segments[0].{key} is {type(val).__name__}, "
                    f"expected float/int"
                )

    return failures


def check_top_level_text(data: dict[str, Any]) -> list[str]:
    """Verify top-level 'text' field exists (used by transcription.py).

    Returns:
        List of failure messages.
    """
    failures: list[str] = []
    if "text" not in data:
        failures.append("MISSING top-level 'text' key")
    elif not isinstance(data["text"], str):
        failures.append(
            f"'text' is {type(data['text']).__name__}, expected str"
        )
    return failures


def run_schema_verification(
    data: dict[str, Any], label: str = ""
) -> tuple[bool, list[str]]:
    """Run all schema checks and print verdicts.

    Args:
        data: The transcription response dict.
        label: Optional label for the verification run.

    Returns:
        Tuple of (passed: bool, all_failures: list[str]).
    """
    print(f"\n{'='*70}")
    print(f"[SCHEMA VERIFICATION] {label}")
    print(f"{'='*70}")

    all_failures: list[str] = []

    # 1. Top-level text
    print("\n--- Check: top-level 'text' field ---")
    failures = check_top_level_text(data)
    all_failures.extend(failures)
    print(f"  Result: {'PASS' if not failures else 'FAIL'}")
    for f in failures:
        print(f"    [X] {f}")

    # 2. Words array (LOAD-BEARING for SubtitleService)
    print("\n--- Check: 'words' array (CRITICAL -- SubtitleService) ---")
    failures = check_words_array(data)
    all_failures.extend(failures)
    print(f"  Result: {'PASS' if not failures else 'FAIL'}")
    for f in failures:
        print(f"    [X] {f}")

    # 3. Segments array
    print("\n--- Check: 'segments' array ---")
    failures = check_segments_array(data)
    all_failures.extend(failures)
    print(f"  Result: {'PASS' if not failures else 'FAIL'}")
    for f in failures:
        print(f"    [X] {f}")

    # Per-model verdict
    print(f"\n  {label} sub-verdict: "
          f"{'PASS' if not all_failures else 'FAIL'} "
          f"({len(all_failures)} issue(s))")

    return len(all_failures) == 0, all_failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """Run the Phase 0 verification gate.

    Tests multiple models and parameter combinations to find any
    configuration that returns word-level timestamps.

    Returns:
        Exit code: 0 = PASS, 1 = FAIL, 2 = API error.
    """
    print("=" * 70)
    print("Phase 0: Pollinations Transcription API Schema Verification")
    print("=" * 70)
    print(f"  Base URL : {BASE_URL}")
    print(f"  API Key  : {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"  Audio    : {TEST_AUDIO_PATH}")
    print(f"  Models   : {MODELS_TO_TEST}")

    # Generate test audio
    generate_test_wav(TEST_AUDIO_PATH)

    # Collect results for each model/config combination
    all_results: list[dict[str, Any]] = []

    for model in MODELS_TO_TEST:
        # --- Config 1: verbose_json + granularities ---
        data = call_transcription(
            TEST_AUDIO_PATH,
            model=model,
            verbose=True,
            granularities=True,
        )

        if data is None:
            # --- Config 2: verbose_json only ---
            print(f"\n[WARN] {model} with granularities failed. "
                  f"Trying verbose_json only...")
            data = call_transcription(
                TEST_AUDIO_PATH,
                model=model,
                verbose=True,
                granularities=False,
            )

        if data is None:
            # --- Config 3: minimal ---
            print(f"\n[WARN] {model} verbose_json failed. "
                  f"Trying minimal params...")
            data = call_transcription(
                TEST_AUDIO_PATH,
                model=model,
                verbose=False,
                granularities=False,
            )

        if data is None:
            print(f"\n[SKIP] All attempts failed for model={model}")
            all_results.append({
                "model": model,
                "data": None,
                "passed": False,
                "failures": ["All API calls failed"],
            })
            continue

        # Dump full raw response
        print(f"\n{'='*70}")
        print(f"[RAW RESPONSE -- model={model} -- Complete JSON]")
        print(f"{'='*70}")
        print(json.dumps(data, indent=4, default=str))

        # Run schema checks
        passed, failures = run_schema_verification(
            data, label=f"model={model}"
        )
        all_results.append({
            "model": model,
            "data": data,
            "passed": passed,
            "failures": failures,
        })

    # -----------------------------------------------------------------------
    # Final consolidated verdict
    # -----------------------------------------------------------------------
    print(f"\n\n{'#'*70}")
    print(f"{'#'*70}")
    print("FINAL CONSOLIDATED VERDICT")
    print(f"{'#'*70}")

    any_passed = False
    best_model = None

    for result in all_results:
        model = result["model"]
        status = "PASS" if result["passed"] else "FAIL"
        print(f"\n  Model: {model} -- {status}")
        if result["failures"]:
            for i, f in enumerate(result["failures"], 1):
                print(f"    {i}. {f}")
        if result["passed"]:
            any_passed = True
            best_model = model

    print(f"\n{'#'*70}")
    if any_passed:
        print(f"[GATE VERDICT] *** PASS ***")
        print(f"  Compatible model: {best_model}")
        print(f"  Schema matches Groq Whisper verbose_json format.")
        print(f"  No normalization layer needed for model={best_model}.")
    else:
        print(f"[GATE VERDICT] *** FAIL ***")
        print(f"  No model returned a schema compatible with SubtitleService.")
        print(f"  A normalization layer IS REQUIRED in transcription.py.")
        print(f"")
        print(f"  Required mapping for production code:")
        # Aggregate unique failures across all models
        unique_failures = set()
        for result in all_results:
            for f in result["failures"]:
                unique_failures.add(f)
        for i, f in enumerate(sorted(unique_failures), 1):
            print(f"    {i}. {f}")

        # If words were empty but the key existed, note the specific issue
        for result in all_results:
            if result["data"] and "words" in result["data"]:
                words = result["data"]["words"]
                if isinstance(words, list) and len(words) == 0:
                    print(f"\n  CRITICAL NOTE for model={result['model']}:")
                    print(f"    'words' key EXISTS but is EMPTY [].")
                    print(f"    Pollinations may not support word-level "
                          f"timestamps with this model.")
                    print(f"    Options:")
                    print(f"      a) Try a different model that supports "
                          f"word timestamps")
                    print(f"      b) Build word-level timestamps from "
                          f"'segments' (lossy)")
                    print(f"      c) Use a different transcription provider "
                          f"for word timestamps")

    print(f"{'#'*70}")

    # Cleanup test audio
    try:
        os.remove(TEST_AUDIO_PATH)
        print(f"\n[CLEANUP] Removed {TEST_AUDIO_PATH}")
    except OSError:
        pass

    return 0 if any_passed else 1


if __name__ == "__main__":
    sys.exit(main())
