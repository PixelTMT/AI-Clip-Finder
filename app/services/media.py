"""FFmpeg helpers for probing, ingesting and slicing project media.

Ingestion honors ``MEDIA_COMPRESS_MODE`` (see :func:`prepare_video`): uploads can
be passed through untouched instead of being re-encoded. In passthrough mode the
original container/codec is preserved as-is, so a format no browser can play
(e.g. HEVC MKV) stays unplayable - ``auto`` exists to avoid exactly that.
"""

import os
import argparse
import json
import logging
import shutil
import ffmpeg

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_video_metadata(input_path: str) -> dict:
    """
    Retrieves video metadata using ffprobe via ffmpeg-python.
    """
    try:
        probe = ffmpeg.probe(input_path)
        format_data = probe.get("format", {})

        metadata = {
            "format": format_data.get("format_name", ""),
            "duration": float(format_data.get("duration", 0)),
            "video_codec": None,
            "audio_codec": None,
            "width": 0,
            "height": 0,
        }

        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video" and not metadata["video_codec"]:
                metadata["video_codec"] = stream.get("codec_name")
                metadata["width"] = stream.get("width", 0)
                metadata["height"] = stream.get("height", 0)
            elif stream.get("codec_type") == "audio" and not metadata["audio_codec"]:
                metadata["audio_codec"] = stream.get("codec_name")

        return metadata
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"FFprobe metadata extraction failed: {err_msg}")


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
    audio_ok = (
        metadata["audio_codec"] is None
        or metadata["audio_codec"] in compatible_audio_codecs
    )

    return container_ok and video_ok and audio_ok


def compress_video(
    input_path: str,
    output_path: str,
    crf: int = None,
    preset: str = None,
    audio_bitrate: str = None,
):
    """
    Re-encodes a video to a web-playable H.264/AAC MP4 using ffmpeg-python.

    Args:
        input_path: Source video path.
        output_path: Destination MP4 path (overwritten if present).
        crf: Constant Rate Factor override. Falls back to ``settings.MEDIA_CRF``.
        preset: x264 preset override (e.g. ``"veryfast"``). Empty/None keeps the
            ffmpeg default, which is what unconfigured installs used before.
        audio_bitrate: AAC bitrate override. Falls back to
            ``settings.MEDIA_AUDIO_BITRATE``.

    Raises:
        RuntimeError: When ffmpeg exits with a non-zero status.
    """
    crf = settings.MEDIA_CRF if crf is None else crf
    audio_bitrate = settings.MEDIA_AUDIO_BITRATE if audio_bitrate is None else audio_bitrate

    output_args = {
        "vsync": "1",
        "vcodec": "libx264",
        "pix_fmt": "yuv420p",
        "rc": "crf",
        "crf": str(crf),
        "acodec": "aac",
        "b:a": audio_bitrate,
        "movflags": "+faststart",
        "threads": 0,
    }
    # Only pass a preset when configured, so the ffmpeg default stays untouched.
    if preset:
        output_args["preset"] = preset

    try:
        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(stream, output_path, **output_args)
        ffmpeg.run(
            stream, overwrite_output=True, capture_stdout=True, capture_stderr=True
        )
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg compression failed: {err_msg}")


def _passthrough(input_path: str, output_path: str):
    """
    Makes ``processed.mp4`` an alias of the uploaded file with no re-encode.

    Uses a hardlink so the operation is instant and costs no extra disk space,
    falling back to a byte copy when the filesystem refuses the link (different
    volume, no hardlink support, ...).

    Args:
        input_path: Uploaded source video path.
        output_path: Destination path expected by the rest of the pipeline.

    Raises:
        RuntimeError: When neither linking nor copying succeeds.
    """
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        logger.info("Media passthrough skipped: input and output are the same file")
        return

    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        os.link(input_path, output_path)
        logger.info("Media passthrough: hardlinked %s -> %s", input_path, output_path)
    except OSError as e:
        logger.warning(
            "Hardlink unavailable (%s): copying %s -> %s instead",
            e,
            input_path,
            output_path,
        )
        try:
            shutil.copy2(input_path, output_path)
        except OSError as copy_error:
            raise RuntimeError(
                f"Media passthrough failed for {input_path}: {copy_error}"
            )
        logger.info("Media passthrough: copied %s -> %s", input_path, output_path)


def prepare_video(input_path: str, output_path: str, mode: str = None):
    """
    Produces ``processed.mp4`` for a fresh upload, re-encoding only when needed.

    Modes:
        ``always``: always re-encode (historical behavior, guaranteed web-playable).
        ``auto``: re-encode only when ffprobe reports an incompatible container
            or codec; otherwise passthrough the original.
        ``never``: always passthrough the original, even when browsers cannot
            play it.

    Args:
        input_path: Uploaded source video path.
        output_path: Destination path expected by the rest of the pipeline.
        mode: Overrides ``settings.MEDIA_COMPRESS_MODE`` when provided.

    Raises:
        RuntimeError: When re-encoding, probing or passthrough fails.
    """
    mode = (mode or settings.MEDIA_COMPRESS_MODE or "always").lower()

    if mode == "never":
        logger.info("MEDIA_COMPRESS_MODE=never: passing upload through untouched")
        _passthrough(input_path, output_path)
        return

    if mode == "auto":
        metadata = get_video_metadata(input_path)
        if is_web_compatible(metadata):
            logger.info(
                "MEDIA_COMPRESS_MODE=auto: %s is already web-compatible "
                "(format=%s video=%s audio=%s), passing through untouched",
                input_path,
                metadata["format"],
                metadata["video_codec"],
                metadata["audio_codec"],
            )
            _passthrough(input_path, output_path)
            return
        logger.info(
            "MEDIA_COMPRESS_MODE=auto: re-encoding %s (format=%s video=%s audio=%s)",
            input_path,
            metadata["format"],
            metadata["video_codec"],
            metadata["audio_codec"],
        )
    else:
        logger.info("MEDIA_COMPRESS_MODE=always: re-encoding %s", input_path)

    compress_video(
        input_path,
        output_path,
        crf=None,
        preset=settings.MEDIA_PRESET,
        audio_bitrate=None,
    )


def extract_audio(input_path: str, output_path: str):
    """
    Extracts audio from video using ffmpeg-python.
    """
    try:
        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(
            stream,
            output_path,
            vn=None,
            acodec="libmp3lame",
            ar="16000",
            ac="1",
            **{"b:a": "48k"},
        )
        ffmpeg.run(
            stream, overwrite_output=True, capture_stdout=True, capture_stderr=True
        )
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg audio extraction failed: {err_msg}")


def extract_frame(input_path: str, time: float, output_path: str):
    """
    Extracts a single frame at a specific time using ffmpeg-python.
    """
    try:
        stream = ffmpeg.input(input_path, ss=time)
        stream = ffmpeg.output(stream, output_path, vframes=1, **{"q:v": 2})
        ffmpeg.run(
            stream, overwrite_output=True, capture_stdout=True, capture_stderr=True
        )
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg frame extraction failed: {err_msg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Media processing utility")
    subparsers = parser.add_subparsers(dest="command")

    # Compress
    p_compress = subparsers.add_parser("compress")
    p_compress.add_argument("input")
    p_compress.add_argument("output")
    p_compress.add_argument(
        "--mode",
        choices=settings.MEDIA_COMPRESS_MODES,
        default=settings.MEDIA_COMPRESS_MODE,
        help=(
            "always: re-encode; auto: re-encode only if not web-compatible; "
            "never: passthrough (default: %(default)s, from MEDIA_COMPRESS_MODE)"
        ),
    )

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
        prepare_video(args.input, args.output, mode=args.mode)
        print(f"Processed {args.input} to {args.output} (mode={args.mode})")
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
