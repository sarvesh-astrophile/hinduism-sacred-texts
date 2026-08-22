#!/usr/bin/env python3
"""Recursively mirror every HTML page under sacred-texts.com/hin/.

Mirrors URL layout into rigveda/raw/, e.g.
    https://sacred-texts.com/hin/maha/maha01.htm -> rigveda/raw/hin/maha/maha01.htm

Already-downloaded pages are parsed from disk (no refetch), so runs are fully
resumable. Only links resolving inside /hin/ are followed."""

import argparse
import random
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://sacred-texts.com"
SCOPE = "/hin/"
OUT_ROOT = Path(__file__).resolve().parent.parent / "rigveda" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) sacred-texts-mirror/1.0"}

session = requests.Session()
session.headers.update(UA)
print_lock = threading.Lock()


def log(msg: str):
    with print_lock:
        print(msg, flush=True)


def dest_for(path: str) -> Path:
    return OUT_ROOT / path.lstrip("/")


def fetch(path: str, retries: int = 6) -> str | None:
    """Fetch /hin/-relative path; returns HTML or None. Skips existing files."""
    dest = dest_for(path)
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.0, 2.0))
            r = session.get(f"{BASE}{path}", timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After") or 0) or min(30 * 2**attempt, 300)
                log(f"429 {path} — backing off {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return r.content
        except Exception as e:
            if attempt == retries - 1:
                log(f"FAILED {path}: {e}")
                return None
            time.sleep(2**attempt)
    return None


def links_in(content: bytes, path: str) -> set[str]:
    """Extract /hin/ HTML-page links from a page."""
    soup = BeautifulSoup(content, "lxml")
    out = set()
    base_url = f"{BASE}{path}"
    for a in soup.find_all("a", href=True):
        try:
            resolved = urlparse(urljoin(base_url, a["href"].strip()))
        except ValueError:
            continue
        if resolved.netloc.lower() != "sacred-texts.com":
            continue
        rp = resolved.path
        if not rp.startswith(SCOPE) or not rp.lower().endswith((".htm", ".html")):
            continue
        out.add(rp)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-pages", type=int, default=0, help="stop after N downloads (0 = unlimited)")
    args = ap.parse_args()

    start = SCOPE + "index.htm"
    queue = deque([start])
    seen = {start}
    downloaded = failed = 0

    def work(path: str):
        data = fetch(path)
        return path, links_in(data, path) if data else None

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        while queue:
            batch = [queue.popleft() for _ in range(min(len(queue), args.workers * 4))]
            futures = [ex.submit(work, p) for p in batch]
            nxt = []
            for fut in as_completed(futures):
                path, found = fut.result()
                if found is None:
                    failed += 1
                    continue
                downloaded += 1
                for link in sorted(found):
                    if link not in seen:
                        seen.add(link)
                        nxt.append(link)
            queue.extend(nxt)
            if args.max_pages and downloaded >= args.max_pages:
                log(f"--max-pages {args.max_pages} reached; stopping discovery")
                break
            log(f"fetched={downloaded} known_pages={len(seen)} queued={len(queue)}")

    log(f"\nDone: {downloaded} pages processed, {failed} failed, {len(seen)} unique pages discovered")


if __name__ == "__main__":
    main()
