#!/usr/bin/env python3
"""Verify and restore the approved media package; optionally rebuild browser clips."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

from media_paths import BUILD, FFMPEG, FFPROBE, HERE


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore(destination: Path, verify_only: bool) -> None:
    manifest = json.loads((HERE / "media-manifest.json").read_text())
    archive = HERE / manifest["archive"]["file"]
    if archive.stat().st_size != manifest["archive"]["bytes"] or digest(archive.read_bytes()) != manifest["archive"]["sha256"]:
        raise ValueError("Archive checksum mismatch.")
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest["files"]):
            raise ValueError("Archive inventory mismatch.")
        # Validate every member and any existing destination before writing.
        for name, expected in manifest["files"].items():
            relative = PurePosixPath(name)
            target = destination / name
            info = package.getinfo(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Unsafe archive member: {name}")
            if not target.resolve().is_relative_to(destination) or target.is_symlink():
                raise ValueError(f"Unsafe destination: {name}")
            data = package.read(name)
            if len(data) != expected["bytes"] or digest(data) != expected["sha256"]:
                raise ValueError(f"Member checksum mismatch: {name}")
            if not verify_only and target.exists() and (not target.is_file() or digest(target.read_bytes()) != expected["sha256"]):
                raise ValueError(f"Refusing to overwrite changed media: {name}")
        if not verify_only:
            for name in names:
                target = destination / name
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(package.read(name))
    print(f"{'Verified' if verify_only else 'Restored'} {len(names)} archived files.")


def browser_clips(destination: Path) -> None:
    from repair_capture import repair

    folder = destination / "capture/repaired"
    for recipe in sorted(folder.glob("*-browser.json")):
        expected = json.loads(recipe.read_text())
        sources = list((destination / "capture/recording").rglob(expected["source_file"]))
        if len(sources) != 1 or digest(sources[0].read_bytes()) != expected["source_sha256"]:
            raise ValueError(f"Source recording mismatch: {recipe.name}")
        target = folder / expected["output_file"]
        if target.exists():
            if digest(target.read_bytes()) != expected["output_sha256"]:
                raise ValueError(f"Refusing to overwrite changed browser clip: {target.name}")
            continue
        # Keep the original recipe immutable while verifying the regenerated clip.
        temporary = folder / ("rebuild-" + target.name)
        try:
            actual = repair(
                sources[0], temporary, FFMPEG, FFPROBE,
                clip_start=expected["reviewed_clip_bounds"]["start"],
                clip_end=expected["reviewed_clip_bounds"]["end"],
                max_gap_seconds=expected.get("reviewed_max_gap_seconds", 0.48),
            )
            if actual["output_frame_count"] != expected["output_frame_count"] or actual["repaired_intervals"] != expected["repaired_intervals"]:
                raise ValueError(f"Browser frame mapping changed: {recipe.name}")
            if actual["output_sha256"] != expected["output_sha256"]:
                raise ValueError(f"Encoded checksum changed; check the recorded FFmpeg version: {recipe.name}")
            temporary.replace(target)
            print(f"Rebuilt and verified {target.name}.", flush=True)
        finally:
            temporary.unlink(missing_ok=True)
            temporary.with_suffix(".json").unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=BUILD)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--browser-clips", action="store_true")
    args = parser.parse_args()
    if args.verify_only and args.browser_clips:
        parser.error("--verify-only cannot rebuild clips.")
    restore(args.destination, args.verify_only)
    if args.browser_clips:
        browser_clips(args.destination.resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
