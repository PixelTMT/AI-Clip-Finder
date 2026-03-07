import os
import sys

# Allow running as standalone script
if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from typing import List, Optional, Dict, Any
import json
import re
import argparse
from openai import OpenAI
from app.core.config import settings


DEFAULT_SYSTEM_PROMPT_TEMPLATE = """
You are an expert video editor and content strategist. Your task is to analyze the provided transcript segments of a video and {clip_instruction}.

Return a JSON list of objects with the following schema:
[
  {{
    "title": "Short, catchy title",
    "score": 1-10 (viral potential),
    "start_time": float (start time in seconds),
    "end_time": float (end time in seconds, REQUIRED),
    "reason": "Why this is a good clip"
  }}
]

Ensure strict JSON format. Do not include any other text. ALWAYS include 'start_time' and 'end_time'.
"""


def clean_json_response(content: str) -> str:
    """Removes markdown code blocks if present."""
    content = content.strip()
    # Remove ```json ... ``` or just ``` ... ```
    if content.startswith("```"):
        # Find the first newline
        first_newline = content.find("\n")
        if first_newline != -1:
            # Remove the first line (```json)
            content = content[first_newline + 1 :]
        # Remove the last ```
        if content.endswith("```"):
            content = content[:-3]
    return content.strip()


def format_segments(segments: list) -> str:
    formatted = []
    for s in segments:
        start = s.get("start", 0)
        end = s.get("end", 0)
        text = s.get("text", "").strip()
        formatted.append(f"[{start:.2f} - {end:.2f}] {text}")
    return "\n".join(formatted)


def analyze_transcript(
    transcript_data: dict,
    custom_instructions: Optional[str] = None,
    clip_count: Optional[int] = None,
) -> list:
    client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)

    if clip_count is None:
        clip_instruction = "identify 3-5 high-impact moments that would make excellent viral clips (e.g., for TikTok, YouTube Shorts, or Instagram Reels)"
    elif clip_count <= 0:
        clip_instruction = "identify as many high-impact moments as you can find from this video transcript"
    else:
        clip_instruction = f"identify exactly {clip_count} high-impact moments from this video transcript"

    system_prompt = DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(
        clip_instruction=clip_instruction
    )

    if custom_instructions:
        system_prompt += f"\n\nAdditional user context: {custom_instructions}"

    # Use segments if available for time context
    segments = transcript_data.get("segments", [])
    if segments:
        user_content = f"TRANSCRIPT SEGMENTS:\n{format_segments(segments)}"
    else:
        # Fallback to plain text if no segments
        user_content = f"TRANSCRIPT:\n{transcript_data.get('text', '')}"

    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        model=settings.LLM_MODEL,
        temperature=0.7,
    )

    content = completion.choices[0].message.content
    if not content:
        print("LLM returned empty content")
        return []

    cleaned_content = clean_json_response(content)

    try:
        clips = json.loads(cleaned_content)

        # Validation
        if not isinstance(clips, list):
            raise ValueError("LLM response is not a list")

        for clip in clips:
            if "end_time" not in clip:
                raise ValueError("Missing required field 'end_time' in clip")
            if "start_time" not in clip:
                raise ValueError("Missing required field 'start_time' in clip")

        return clips
    except json.JSONDecodeError:
        print(f"Failed to parse JSON: {content}")
        return []


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Clip Analysis")
    parser.add_argument("transcript_file", help="Path to transcript JSON file")
    parser.add_argument("--custom", help="Custom instructions", default=None)
    args = parser.parse_args()

    try:
        with open(
            "D:\\Coding\\Python\\AI-clip\\data\\projects\\77424871-e1fb-4aca-9c30-256f050e078f\\audio.mp3.json",
            "r",
        ) as f:
            data = json.load(f)

        clips = analyze_transcript(data, "")
        print(json.dumps(clips, indent=2))
    except Exception as e:
        print(f"Error: {e}")
