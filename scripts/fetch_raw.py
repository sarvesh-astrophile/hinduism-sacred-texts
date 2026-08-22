#!/usr/bin/env python3
"""Download the raw HTML of the Rig Veda (Griffith English + Sanskrit) from
sacred-texts.com, mirroring the site layout under rigveda/raw/.

    rigveda/raw/hin/rigveda/   index.htm, rvi01..10.htm, rvBBHHH.htm  (English)
    rigveda/raw/hin/rvsan/     rvBBHHH.htm                            (Sanskrit)

Existing files are skipped, so the run is resumable."""

import argparse
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://sacred-texts.com"
EN_PATH = "hin/rigveda"
SA_PATH = "hin/rvsan"
OUT_ROOT = Path(__file__).resolve().parent.parent / "rigveda" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) sacred-texts-mirror/1.0"}

session = requests.Session()
session.headers.update(UA)


def fetch(url: str, dest: Path, retries: int = 6) -> bool:
    """Download url to dest unless it already exists. True on success/skip."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(0.5, 1.0))
            r = session.get(url, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After") or 0) or min(30 * 2**attempt, 300)
                print(f"429 {url} — backing off {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return True
        except Exception as e:
            if attempt == retries - 1:
                print(f"FAILED {url}: {e}", file=sys.stderr)
                return False
            time.sleep(2**attempt)
    return False


def hymn_urls(book: int) -> list[str]:
    """Discover hymn page names from book index rviNN.htm."""
    idx_name = f"rvi{book:02d}.htm"
    ok = fetch(f"{BASE}/{EN_PATH}/{idx_name}", OUT_ROOT / EN_PATH / idx_name)
    if not ok:
        print(f"Book {book}: index fetch failed", file=sys.stderr)
        return []
    html = (OUT_ROOT / EN_PATH / idx_name).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    names = sorted(
        {
            m.group(0)
            for a in soup.find_all("a", href=re.compile(rf"^rv{book:02d}\d{{3}}\.htm$"))
            if (m := re.fullmatch(rf"rv{book:02d}\d{{3}}\.htm", a["href"]))
        }
    )
    return [f"{n}" for n in names]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="1-10", help="e.g. '1-10' or '1,9,10'")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--skip-sanskrit", action="store_true")
    args = ap.parse_args()

    if "-" in args.books:
        lo, hi = args.books.split("-")
        wanted = list(range(int(lo), int(hi) + 1))
    else:
        wanted = [int(x) for x in args.books.split(",")]

    jobs = [(f"{BASE}/index.htm", OUT_ROOT / "index.htm"),
            (f"{BASE}/{EN_PATH}/index.htm", OUT_ROOT / EN_PATH / "index.htm")]
    total_hymns = 0
    for b in wanted:
        names = hymn_urls(b)
        print(f"Book {b}: {len(names)} hymns")
        total_hymns += len(names)
        for n in names:
            jobs.append((f"{BASE}/{EN_PATH}/{n}", OUT_ROOT / EN_PATH / n))
            if not args.skip_sanskrit:
                jobs.append((f"{BASE}/{SA_PATH}/{n}", OUT_ROOT / SA_PATH / n))

    print(f"{len(jobs)} pages to ensure (~{total_hymns} hymns x2 + indexes)")
    done = fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(fetch, u, d): u for u, d in jobs}
        for fut in as_completed(futures):
            done += 1
            if not fut.result():
                fail += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)}")

    print(f"\nDone: {done - fail}/{len(jobs)} ok, {fail} failed")


if __name__ == "__main__":
    main()
