#!/usr/bin/env python3
"""Synthesize approved per-slide narration, keeping credentials in memory."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
import re
import urllib.error
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

HOSTS = {"global": "https://api.minimax.io", "china": "https://api.minimaxi.com",
         "west": "https://api-uw.minimax.io"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward authorization to a redirect target.


class APIError(Exception):
    def __init__(self, status, message, http_status=None):
        super().__init__(message)
        self.status, self.http_status = status, http_status


def scrub(message: str, key: str) -> str:
    if key:
        message = message.replace(key, "[REDACTED]")
    message = re.sub(r"sk-api-[A-Za-z0-9_-]+", "[REDACTED]", message)
    return re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", message)[:600]


def post(host: str, path: str, payload: dict, key: str) -> dict:
    req = urllib.request.Request(
        host + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=90) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw)
            base = data.get("base_resp", {})
            message = base.get("status_msg") or data.get("message") or "HTTP request rejected"
            raise APIError(base.get("status_code"), str(message), exc.code) from None
        except (ValueError, AttributeError):
            raise APIError(None, "HTTP request rejected (non-JSON response)", exc.code) from None
    data = json.loads(raw)
    base = data.get("base_resp", {})
    if base.get("status_code") != 0:
        raise APIError(base.get("status_code"), str(base.get("status_msg", "API rejected request")))
    return data




def save_json(path: Path, value: dict | list) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def page_numbers(spec: str) -> set[int]:
    result = set()
    for part in spec.split(","):
        bounds = [int(x) for x in part.split("-")]
        result.update(range(bounds[0], bounds[-1] + 1))
    return result


def download_subtitles(url: str) -> dict | list:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise ValueError("Subtitle response did not contain an HTTPS download URL")
    # The URL comes from the authenticated MiniMax response. No API credentials
    # are attached to the generated file's CDN request or retained in metadata.
    request = urllib.request.Request(url, headers={"User-Agent": "gherkai-video-production"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=45) as response:
        data = response.read(10 * 1024 * 1024)
    return json.loads(data.decode("utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--pages", help="Optional page numbers/ranges; defaults to all pages")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pause-after-preview", action="store_true")
    args = parser.parse_args()
    base = args.manifest.resolve().parent
    manifest = json.loads(args.manifest.read_text())
    settings = dict(manifest["style"])
    settings["voice_id"] = os.environ.get("MINIMAX_VOICE_ID", settings.get("voice_id", ""))
    selected = [p for p in manifest["pages"] if not args.pages or p["page"] in page_numbers(args.pages)]
    if not selected:
        raise ValueError("No matching pages")
    key = ""
    try:
        for page in selected:
            text = page["text"]
            if not 0 < len(text) < 10000:
                raise ValueError("Narration length is outside API limits")
            if hashlib.sha256(text.encode()).hexdigest() != page["text_sha256"]:
                raise ValueError("Approved narration hash mismatch")
        if args.dry_run:
            print(json.dumps({"status": "dry_run", "pages": [p["page"] for p in selected],
                              "characters": sum(len(p["text"]) for p in selected),
                              "style": settings}, ensure_ascii=False))
            return 0
        if not settings["voice_id"]:
            raise ValueError("Provide MINIMAX_VOICE_ID before synthesis")
        key = os.environ.get("MINIMAX_API_KEY", "").strip()
        if not key:
            if not sys.stdin.isatty():
                raise ValueError("Use an interactive terminal or MINIMAX_API_KEY")
            key = getpass.getpass("MiniMax key (hidden, memory only): ").strip()
        if not key:
            raise ValueError("No key supplied")
        preview_paused = False
        for page in selected:
            number = page["page"]
            audio_path = base / page["audio_file"]
            metadata_path = audio_path.with_suffix(".json")
            subtitles_path = audio_path.with_suffix(".subtitles.json")
            attempt_path = audio_path.with_suffix(".attempt.json")
            if audio_path.exists() and metadata_path.exists() and subtitles_path.exists():
                metadata = json.loads(metadata_path.read_text())
                if metadata["text_sha256"] != page["text_sha256"]:
                    raise ValueError(f"Existing narration differs on page {number}")
                print(json.dumps({"page": number, "status": "reused"}), flush=True)
                continue
            if attempt_path.exists() or audio_path.exists() or metadata_path.exists():
                raise ValueError(f"Page {number} has a prior or incomplete attempt; no automatic paid retry")
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "model": settings["model"],
                "text": page["text"],
                "stream": False,
                "output_format": "hex",
                "language_boost": "Chinese",
                "voice_setting": {
                    "voice_id": settings["voice_id"],
                    "speed": settings["speed"],
                    "emotion": settings["emotion"],
                    "vol": 1,
                    "pitch": 0,
                },
                "audio_setting": {
                    "sample_rate": 44100, "bitrate": 128000,
                    "format": "mp3", "channel": 1,
                },
                "subtitle_enable": True,
                "subtitle_type": "word",
            }
            pronunciation = manifest.get("pronunciation_dict")
            if pronunciation:
                payload["pronunciation_dict"] = pronunciation
            save_json(attempt_path, {
                "page": number, "started_utc": datetime.now(timezone.utc).isoformat(),
                "text_sha256": page["text_sha256"], "paid_retry": False,
            })
            print(json.dumps({"page": number, "status": "synthesizing",
                              "characters": len(page["text"])}), flush=True)
            started = time.monotonic()
            response = post(HOSTS[settings["region"]], "/v1/t2a_v2", payload, key)
            data = response.get("data") or {}
            if data.get("status") != 2 or not data.get("audio"):
                raise ValueError(f"Page {number}: no completed audio returned")
            audio = bytes.fromhex(data["audio"])
            if len(audio) < 128:
                raise ValueError(f"Page {number}: audio result is too short")
            with audio_path.open("xb") as out:
                out.write(audio)
            metadata = {
                "status": "success", "page": number,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "text_sha256": page["text_sha256"],
                "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "audio_bytes": len(audio), "style": settings,
                "pronunciation_dict": pronunciation,
                "request_seconds": round(time.monotonic() - started, 3),
                "trace_id": response.get("trace_id"),
                "extra_info": response.get("extra_info"),
            }
            save_json(metadata_path, metadata)
            subtitle_file = data.get("subtitle_file")
            if not subtitle_file:
                raise ValueError(f"Page {number}: audio saved, but subtitle file was not returned")
            subtitle_data = download_subtitles(subtitle_file)
            save_json(subtitles_path, subtitle_data)
            print(json.dumps({"page": number, "status": "success",
                              "audio_bytes": len(audio),
                              "extra_info": response.get("extra_info"),
                              "subtitle_container": type(subtitle_data).__name__},
                             ensure_ascii=False), flush=True)
            if args.pause_after_preview and not preview_paused:
                preview_paused = True
                input("Preview saved. Press Enter to continue the remaining pages: ")
        return 0
    except APIError as exc:
        print(json.dumps({"status": "api_error", "http_status": exc.http_status,
                          "api_status_code": exc.status,
                          "message": scrub(str(exc), key), "retried": False},
                         ensure_ascii=False), file=sys.stderr)
        return 1
    except Exception as exc:
        # Avoid logging signed download URLs or credential-bearing objects.
        message = scrub(str(exc), key)
        if isinstance(exc, urllib.error.URLError):
            message = f"Network request failed ({type(exc).__name__}); completed audio is retained"
        print(json.dumps({"status": "error", "message": message, "retried": False},
                         ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        key = ""


if __name__ == "__main__":
    raise SystemExit(main())
