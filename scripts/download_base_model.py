#!/usr/bin/env python3
"""
Resilient downloader for the DistilBERT base model.

On flaky networks the plain Hugging Face download can reset at byte 0 and never
progress. This script fetches each required file with HTTP Range **resume** and
many retries, so a dropped connection just continues from where it left off.

Files land in ./models/base-distilbert, which you then pass to training via
--base-model (or BASE_MODEL env).

Usage:
    python scripts/download_base_model.py
"""
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = "distilbert-base-uncased"
BASE_URL = f"https://huggingface.co/{REPO}/resolve/main"
FILES = [
    "config.json",
    "vocab.txt",
    "tokenizer_config.json",
    "tokenizer.json",
    "model.safetensors",
]
OUT = Path(__file__).resolve().parent.parent / "models" / "base-distilbert"
MAX_RETRIES = 200
CHUNK = 1024 * 256  # 256 KB


def _remote_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "ticketai-downloader/1.0")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0))


def download(url: str, dest: Path):
    total = 0
    try:
        total = _remote_size(url)
    except Exception:
        pass

    for attempt in range(1, MAX_RETRIES + 1):
        have = dest.stat().st_size if dest.exists() else 0
        if total and have >= total:
            print(f"  done: {dest.name} ({have/1e6:.1f} MB)")
            return
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "ticketai-downloader/1.0")
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                mode = "ab" if have else "wb"
                with open(dest, mode) as f:
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        if total:
                            pct = 100 * have / total
                            print(f"\r  {dest.name}: {have/1e6:7.1f}/{total/1e6:.1f} MB ({pct:5.1f}%)",
                                  end="", flush=True)
            print()
            if not total or have >= total:
                print(f"  done: {dest.name}")
                return
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            wait = min(5, 0.5 * attempt)
            print(f"\n  [{dest.name}] reset at {have/1e6:.1f} MB (attempt {attempt}/{MAX_RETRIES}) "
                  f"— resuming in {wait:.1f}s... ({e})")
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {dest.name} after {MAX_RETRIES} attempts")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO} -> {OUT}")
    for name in FILES:
        download(f"{BASE_URL}/{name}", OUT / name)
    print(f"\nAll files present in {OUT}")
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name:24s} {p.stat().st_size/1e6:8.2f} MB")


if __name__ == "__main__":
    main()
