import os
import subprocess
import argparse
import json

def get_video_metadata(input_path: str) -> dict:
    """
    Retrieves video metadata using ffprobe.
    """
    ffprobe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        input_path
    ]
    
    try:
        result = subprocess.run(ffprobe_cmd, check=True, capture_output=True)
        data = json.loads(result.stdout)
        
        metadata = {
            "format": data.get("format", {}).get("format_name", ""),
            "duration": float(data.get("format", {}).get("duration", 0)),
            "video_codec": None,
            "audio_codec": None,
            "width": 0,
            "height": 0
        }
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and not metadata["video_codec"]:
                metadata["video_codec"] = stream.get("codec_name")
                metadata["width"] = stream.get("width", 0)
                metadata["height"] = stream.get("height", 0)
            elif stream.get("codec_type") == "audio" and not metadata["audio_codec"]:
                metadata["audio_codec"] = stream.get("codec_name")
                
        return metadata
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"FFprobe metadata extraction failed: {str(e)}")

def is_web_compatible(metadata: dict) -> bool:
    """
    Checks if the video is web-compatible based on container and codecs.
    """
    compatible_containers = ["mp4", "webm"]
    compatible_video_codecs = ["h264", "vp8", "vp9", "av1"]
    compatible_audio_codecs = ["aac", "opus", "vorbis"]
    
    # Check container
    container_ok = any(c in metadata["format"].lower() for c in compatible_containers)
    
    # Check video codec
    video_ok = metadata["video_codec"] in compatible_video_codecs
    
    # Check audio codec (can be None if silent)
    audio_ok = metadata["audio_codec"] is None or metadata["audio_codec"] in compatible_audio_codecs
    
    return container_ok and video_ok and audio_ok

def compress_video(input_path: str, output_path: str):
    # -y to overwrite, -i for input, -vcodec libx264 for web compatibility, -crf 28 for compression
    ffmpeg_cmd = [
        "ffmpeg", "-y", 
        "-i", input_path,
        "-vsync", "1",               
        "-vcodec", "libx264", # Reverted to libx264 for broader compatibility if h264_amf fails on some systems
        "-pix_fmt", "yuv420p", 
        "-rc", "crf",                
        "-crf", "32",
        "-acodec", "aac", 
        "-b:a", "128k",
        "-movflags", "+faststart", 
        "-threads", "0",
        output_path
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg compression failed: {e.stderr.decode()}")

def extract_audio(input_path: str, output_path: str):
    ffmpeg_cmd = [
        "ffmpeg", "-y", 
        "-i", input_path,
        "-vn",                   
        "-acodec", "libmp3lame",
        "-ar", "16000",          
        "-ac", "1",              
        "-b:a", "48k",    # 48k for clear audio, 32k for "safety," still tiny
        output_path
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg audio extraction failed: {e.stderr.decode()}")

def extract_frame(input_path: str, time: float, output_path: str):
    # -ss time -i input -frames:v 1 -q:v 2 output
    ffmpeg_cmd = [
        "ffmpeg", "-y", 
        "-ss", str(time),
        "-i", input_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg frame extraction failed: {e.stderr.decode()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Media processing utility")
    subparsers = parser.add_subparsers(dest="command")
    
    # Compress
    p_compress = subparsers.add_parser("compress")
    p_compress.add_argument("input")
    p_compress.add_argument("output")
    
    # Extract Audio
    p_audio = subparsers.add_parser("audio")
    p_audio.add_argument("input")
    p_audio.add_argument("output")
    
    # Extract Frame
    p_frame = subparsers.add_parser("frame")
    p_frame.add_argument("input")
    p_frame.add_argument("time", type=float)
    p_frame.add_argument("output")
    
    # Inspect
    p_inspect = subparsers.add_parser("inspect")
    p_inspect.add_argument("input")
    
    args = parser.parse_args()
    
    if args.command == "compress":
        compress_video(args.input, args.output)
        print(f"Compressed {args.input} to {args.output}")
    elif args.command == "audio":
        extract_audio(args.input, args.output)
        print(f"Extracted audio from {args.input} to {args.output}")
    elif args.command == "frame":
        extract_frame(args.input, args.time, args.output)
        print(f"Extracted frame at {args.time}s from {args.input} to {args.output}")
    elif args.command == "inspect":
        metadata = get_video_metadata(args.input)
        print(json.dumps(metadata, indent=2))
        print(f"Web compatible: {is_web_compatible(metadata)}")
    else:
        parser.print_help()