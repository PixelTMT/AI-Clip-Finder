import os
import json
import argparse
from groq import Groq

def transcribe_audio(file_path: str):
    # Check for cached transcription
    cache_path = f"{file_path}.json"
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass # corrupted cache, proceed to re-transcribe

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY", "dummy_key_for_test")
    )
    
    with open(file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities = ["word", "segment"], # Optional (must set response_format to "json" to use and can specify "word", "segment" (default), or both)
            language="en",  # Optional
            temperature=0.0  # Optional
        )
    
    # Convert object to dict for easier handling
    data = transcription.model_dump()

    # 2. Save it to a file with 4-space indentation
    with open(f"{cache_path.replace(".json", "_raw.json")}", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    
    with open(f"{cache_path.replace(".json", "_raw.json")}", "r") as file:
        # Use json.load() to read the file and convert the data
        raw_data = json.load(file)
        result = {
            "text": raw_data["text"],
            "segments": [
                {
                    "start": s["start"],
                    "end": s["end"],
                    "text": s["text"]
                } for s in raw_data["segments"]
            ]
        }
    
    # Save to cache
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=4)
        
    return result

if __name__ == "__main__":    
    try:
        res = transcribe_audio("audio.mp3")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")