"""Verifies that upload ingestion respects MEDIA_COMPRESS_MODE.

Generates throwaway media with ffmpeg, runs the real ``prepare_video`` code path
for each mode and asserts on the resulting ``processed.mp4``. Requires ffmpeg in
PATH. Run standalone: ``python tests/verify_media_mode.py``.
"""

import hashlib
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow running as a standalone script from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ffmpeg

import app.core.config as config_module
import app.services.media as media_module

_ORIGINAL_MODE = os.environ.get("MEDIA_COMPRESS_MODE")


def _make_web_video(path: Path) -> None:
    """Writes a tiny H.264/AAC MP4 that browsers can play."""
    video, audio = _lavfi_inputs()
    _run(
        ffmpeg.output(
            video,
            audio,
            str(path),
            vcodec="libx264",
            pix_fmt="yuv420p",
            acodec="aac",
            shortest=None,
        )
    )


def _make_legacy_video(path: Path) -> None:
    """Writes an MPEG-4/MP3 AVI that browsers cannot play."""
    video, audio = _lavfi_inputs()
    _run(
        ffmpeg.output(
            video, audio, str(path), vcodec="mpeg4", acodec="libmp3lame", shortest=None
        )
    )


def _lavfi_inputs():
    """Synthetic 2s test source: colour bars + tone."""
    return (
        ffmpeg.input("testsrc=size=320x240:rate=15:duration=2", f="lavfi"),
        ffmpeg.input("sine=frequency=440:duration=2", f="lavfi"),
    )


def _run(stream, timeout: int = 120) -> None:
    """Runs an ffmpeg spec, converting failures and hangs into loud errors."""
    args = ffmpeg.compile(stream)
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s: {' '.join(args)}")
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace")
        raise RuntimeError(f"ffmpeg failed (rc={proc.returncode}): {stderr[-800:]}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_never_mode_passes_upload_through(tmp_path: Path):
    """never: processed file is byte-identical to the upload."""
    source = tmp_path / "original.mp4"
    target = tmp_path / "processed.mp4"
    _make_legacy_video(source)

    media_module.prepare_video(str(source), str(target), mode="never")

    assert target.exists(), "processed.mp4 was not created"
    assert _sha256(target) == _sha256(source), "never mode altered the file bytes"


def test_auto_mode_skips_reencode_for_compatible_upload(tmp_path: Path):
    """auto + web-playable upload: no re-encode at all."""
    source = tmp_path / "original.mp4"
    target = tmp_path / "processed.mp4"
    _make_web_video(source)
    assert media_module.is_web_compatible(media_module.get_video_metadata(str(source)))

    media_module.prepare_video(str(source), str(target), mode="auto")

    assert target.exists(), "processed.mp4 was not created"
    assert _sha256(target) == _sha256(source), "auto mode re-encoded a compatible video"


def test_auto_mode_reencodes_incompatible_upload(tmp_path: Path):
    """auto + non-web upload: re-encoded into a web-compatible MP4."""
    source = tmp_path / "original.avi"
    target = tmp_path / "processed.mp4"
    _make_legacy_video(source)
    assert not media_module.is_web_compatible(media_module.get_video_metadata(str(source)))

    media_module.prepare_video(str(source), str(target), mode="auto")

    assert target.exists(), "processed.mp4 was not created"
    assert _sha256(target) != _sha256(source), "auto mode failed to re-encode an AVI"
    result = media_module.get_video_metadata(str(target))
    assert media_module.is_web_compatible(result), result


def test_always_mode_reencodes_compatible_upload(tmp_path: Path):
    """always (default): re-encode even when the upload already plays."""
    source = tmp_path / "original.mp4"
    target = tmp_path / "processed.mp4"
    _make_web_video(source)

    media_module.prepare_video(str(source), str(target), mode="always")

    assert target.exists(), "processed.mp4 was not created"
    assert _sha256(target) != _sha256(source), "always mode skipped the re-encode"
    result = media_module.get_video_metadata(str(target))
    assert media_module.is_web_compatible(result), result


def test_passthrough_replaces_stale_processed_file(tmp_path: Path):
    """A leftover processed.mp4 from an earlier mode must not survive."""
    source = tmp_path / "original.mp4"
    target = tmp_path / "processed.mp4"
    _make_web_video(source)
    target.write_bytes(b"stale bytes")

    media_module.prepare_video(str(source), str(target), mode="never")

    assert _sha256(target) == _sha256(source), "stale processed.mp4 was not replaced"


def test_invalid_mode_env_falls_back_to_always():
    """A typo in MEDIA_COMPRESS_MODE must be loud, not fatal."""
    try:
        os.environ["MEDIA_COMPRESS_MODE"] = "alwyas"
        importlib.reload(config_module)
        assert config_module.settings.MEDIA_COMPRESS_MODE == "always", (
            config_module.settings.MEDIA_COMPRESS_MODE
        )
    finally:
        if _ORIGINAL_MODE is None:
            os.environ.pop("MEDIA_COMPRESS_MODE", None)
        else:
            os.environ["MEDIA_COMPRESS_MODE"] = _ORIGINAL_MODE
        importlib.reload(config_module)


if __name__ == "__main__":
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found in PATH")

    workdir = Path(tempfile.mkdtemp(prefix="verify_media_mode_"))

    def case(name: str) -> Path:
        """Isolated directory per check, so fixtures never collide."""
        path = workdir / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    checks = [
        ("never_mode_passthrough", test_never_mode_passes_upload_through),
        ("auto_mode_skips_reencode", test_auto_mode_skips_reencode_for_compatible_upload),
        ("auto_mode_reencodes", test_auto_mode_reencodes_incompatible_upload),
        ("always_mode_reencodes", test_always_mode_reencodes_compatible_upload),
        ("passthrough_replaces_stale", test_passthrough_replaces_stale_processed_file),
    ]
    try:
        for name, check in checks:
            print(f"running {name}...")
            check(case(name))
        print("running invalid_mode_env...")
        test_invalid_mode_env_falls_back_to_always()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    print("OK: media compress mode checks passed")
