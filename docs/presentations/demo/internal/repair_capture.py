#!/usr/bin/env python3
"""Repair short Live View capture gaps, preserving provenance.

Only use after confirming that the remote browser chrome disappears in gaps.
This is not a general deflicker filter: it must not conceal application failures.
Originals stay unchanged. Long interior gaps are rejected; blank connection
headers/tails are trimmed. Explicit clip bounds require visual review.
Requires FFmpeg/ffprobe and numpy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np


def groups(mask: np.ndarray) -> list[tuple[int, int]]:
    boundaries = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(boundaries == 1), np.flatnonzero(boundaries == -1)))


def digest(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def repair(
    source: Path, destination: Path, ffmpeg: str, ffprobe: str,
    clip_start: float | None = None, clip_end: float | None = None,
    max_gap_seconds: float = 0.48,
) -> dict:
    if source.resolve() == destination.resolve():
        raise ValueError("Keep the original recording; choose a separate destination.")
    if not 0 < max_gap_seconds <= 1:
        raise ValueError("Only reviewed capture gaps of at most one second are supported.")
    probe = json.loads(subprocess.check_output([
        ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,r_frame_rate,avg_frame_rate", "-of", "json", str(source),
    ]))["streams"][0]
    assert probe["r_frame_rate"] == probe["avg_frame_rate"] == "25/1", (
        "Frame mapping currently requires the original constant 25 fps recording."
    )
    width, height, fps = probe["width"], probe["height"], 25
    small = subprocess.check_output([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", "scale=160:90:flags=area", "-an", "-fps_mode", "passthrough",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    frames = np.frombuffer(small, dtype=np.uint8).reshape(-1, 90, 160, 3)
    # These sources are full-browser 1456x818 captures with 86px browser chrome.
    # Some failed draws retain a rectangular app tile but lose all chrome.
    # An ordinary white app page retains its tab/address bar and is not a gap.
    assert (width, height) == (1456, 818), "Review chrome geometry for a new source."
    white_fraction = (frames.min(axis=3) > 230).mean(axis=(1, 2))
    spatial_std = frames.astype(np.float32).std(axis=(1, 2)).max(axis=1)
    chrome = frames[:, :9]
    chrome_white = (chrome.min(axis=3) > 230).mean(axis=(1, 2))
    chrome_std = chrome.astype(np.float32).std(axis=(1, 2)).max(axis=1)
    blank = ((white_fraction > 0.985) & (spatial_std < 8)) | (
        (chrome_white > 0.985) & (chrome_std < 8)
    )
    intervals = groups(blank)
    start, end = 0, len(frames)
    for left, right in intervals:
        if left <= fps and right - left > fps:
            start = int(right)
        if right == len(frames) and right - left > fps:
            end = int(left)
    if clip_start is not None:
        start = round(clip_start * fps)
    if clip_end is not None:
        end = round(clip_end * fps)
    assert 0 <= start < end <= len(frames)
    assert start < end and not blank[start]
    repairs = []
    for left, right in intervals:
        if right <= start or left >= end:
            continue
        assert right - left <= round(max_gap_seconds * fps), (
            f"Interior gap at {left / fps:.2f}s lasts {(right-left) / fps:.2f}s; "
            "do not conceal a longer loss of recording."
        )
        repairs.append({
            "source_start_frame": int(left), "source_end_frame_exclusive": int(right),
            "held_source_frame": int(left - 1),
            "source_start_seconds": float(left / fps),
            "duration_seconds": float((right - left) / fps),
        })
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".encoding.mp4")
    decoder = subprocess.Popen([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-an", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], stdout=subprocess.PIPE)
    encoder = subprocess.Popen([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
    ], stdin=subprocess.PIPE)
    count = 0
    last_good = None
    frame_bytes = width * height * 3
    try:
        for index in range(len(frames)):
            data = decoder.stdout.read(frame_bytes)
            assert len(data) == frame_bytes, f"Incomplete decoded frame {index}"
            if not start <= index < end:
                continue
            if blank[index]:
                assert last_good is not None
                encoder.stdin.write(last_good)
            else:
                encoder.stdin.write(data)
                last_good = data
            count += 1
        assert not decoder.stdout.read(1)
        encoder.stdin.close()
        assert decoder.wait() == encoder.wait() == 0
        assert count == end - start
    except BaseException:
        decoder.kill()
        encoder.kill()
        decoder.wait()
        encoder.wait()
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(destination)
    manifest = {
        "source_file": source.name, "source_sha256": digest(source),
        "output_file": destination.name, "output_sha256": digest(destination),
        "fps": fps, "source_frame_count": len(frames), "output_frame_count": count,
        "source_start_frame": start, "source_end_frame_exclusive": end,
        "source_start_seconds": start / fps, "source_end_seconds": end / fps,
        "duration_seconds": count / fps,
        "repaired_intervals": repairs,
        "replaced_frames": sum(
            r["source_end_frame_exclusive"] - r["source_start_frame"] for r in repairs
        ),
        "method": (
            "Hold the preceding real frame across each short, uniformly white "
            "browser-chrome capture gap, including incomplete rectangular draws. "
            "Preserve elapsed time within the retained "
            "interval. Trim blank connection setup/teardown only. No interpolation, "
            "generated application pixels, application edits, or result edits."
        ),
        "reviewed_clip_bounds": {"start": clip_start, "end": clip_end},
        "reviewed_max_gap_seconds": max_gap_seconds,
        "root_cause_limit": (
            "White gaps occur in the original Live View capture and also remove "
            "the remote browser chrome. The precise streaming/rendering/recorder "
            "component has not been isolated."
        ),
    }
    destination.with_suffix(".json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--clip-start", type=float)
    parser.add_argument("--clip-end", type=float)
    parser.add_argument("--max-gap-seconds", type=float, default=0.48)
    args = parser.parse_args()
    result = repair(
        args.source, args.destination, args.ffmpeg, args.ffprobe,
        args.clip_start, args.clip_end, args.max_gap_seconds,
    )
    print(json.dumps({
        "output": str(args.destination),
        "replaced_frames": result["replaced_frames"],
        "gap_count": len(result["repaired_intervals"]),
        "duration_seconds": result["duration_seconds"],
    }))
