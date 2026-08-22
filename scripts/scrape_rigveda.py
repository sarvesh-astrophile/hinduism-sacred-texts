#!/usr/bin/env python3
"""Download the Rig Veda (Griffith 1896, English + Sanskrit) from sacred-texts.com
and emit organized Markdown files under rigveda/."""

import argparse
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

BASE = "https://sacred-texts.com/hin"
EN_DIR = f"{BASE}/rigveda"
SA_DIR = f"{BASE}/rvsan"
CACHE = Path("/tmp/opencode/rigveda_cache")
OUT_ROOT = Path(__file__).resolve().parent.parent / "rigveda"

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
ROMAN_TITLE = re.compile(r"^HYMN\s+[IVXLC]+\.\s*", re.IGNORECASE)
VERSE_START = re.compile(r"^(\d+)[.)]?\s+(.*)$")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) rigveda-md-scraper/1.0"}

session = requests.Session()
session.headers.update(UA)


def fetch(url: str, subdir: str, retries: int = 6) -> str | None:
    """Fetch a page with a file cache; returns HTML text or None on failure."""
    name = url.rsplit("/", 1)[-1]
    cache_path = CACHE / subdir / name
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(0.6, 1.4))
            r = session.get(url, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After") or 0) or min(30 * 2**attempt, 300)
                print(f"429 {url} — backing off {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            r.raise_for_status()
            html = r.content.decode("utf-8", errors="replace")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(html, encoding="utf-8")
            return html
        except Exception as e:
            if attempt == retries - 1:
                print(f"FAILED {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2**attempt)


def crawl_book_index(book: int) -> list[dict]:
    """Parse rviNN.htm into a list of {hymn, title, en_url, sa_url}."""
    html = fetch(f"{EN_DIR}/rvi{book:02d}.htm", "idx")
    soup = BeautifulSoup(html, "lxml")
    hymns = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(rf"^rv{book:02d}\d{{3}}\.htm$")):
        m = re.search(r"rv(\d{2})(\d{3})\.htm", a["href"])
        b, h = int(m.group(1)), int(m.group(2))
        if h in seen:
            continue
        seen.add(h)
        title = ROMAN_TITLE.sub("", a.get_text(strip=True)).strip().rstrip(".") or str(h)
        hymns.append(
            {
                "book": b,
                "hymn": h,
                "title": title,
                "en_url": f"{EN_DIR}/rv{b:02d}{h:03d}.htm",
                "sa_url": f"{SA_DIR}/rv{b:02d}{h:03d}.htm",
            }
        )
    hymns.sort(key=lambda x: x["hymn"])
    return hymns


def parse_english(html: str) -> tuple[str | None, list[tuple[int, list[str]]]]:
    """Return (title, [(verse_num, [lines])]) from an English hymn page."""
    soup = BeautifulSoup(html, "lxml")
    h3 = soup.find("h3")
    title = h3.get_text(strip=True) if h3 else None
    content = None
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=False).strip()
        if re.match(r"^\d+\s", text):
            content = p
            break
    verses = []
    if content is None:
        return title, verses
    lines = []
    for seg in content:
        if getattr(seg, "name", None) == "br":
            continue
        chunk = seg.get_text() if hasattr(seg, "get_text") else str(seg)
        for piece in str(chunk).split("\n"):
            for line in piece.split("<br>"):
                lines.extend(line.strip("\r\n").split("\n"))
    cur_num, cur_lines = None, []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = VERSE_START.match(line)
        if m and (cur_num is None or int(m.group(1)) == cur_num + 1):
            if cur_num is not None:
                verses.append((cur_num, cur_lines))
            cur_num, cur_lines = int(m.group(1)), [m.group(2).strip()]
        elif cur_num is not None:
            cur_lines.append(line)
    if cur_num is not None:
        verses.append((cur_num, cur_lines))
    return title, verses


def _sa_lines(html: str) -> list[str]:
    """Collect the raw verse lines following the <h3> on a Sanskrit page."""
    soup = BeautifulSoup(html, "lxml")
    h3 = soup.find("h3")
    lines = []
    buf = []
    for node in h3.next_siblings if h3 else []:
        name = getattr(node, "name", None)
        if name in ("hr", "table", "div", "nav", "script", "center"):
            break
        if name == "br":
            line = " ".join(buf).strip()
            if line:
                lines.append(line)
            buf = []
        elif name is None:
            buf.extend(str(node).strip().split("\n"))
        elif not node.get_text(strip=True):
            continue
        else:
            break
    tail = " ".join(buf).strip()
    if tail:
        lines.append(tail)
    return [re.sub(r"\s+", " ", ln) for ln in lines]


def parse_sanskrit(html: str) -> tuple[list[list[str]], list[list[str]]]:
    """Split Sanskrit page lines into (devanagari_verses, iast_verses); each verse is [lines]."""
    lines = _sa_lines(html)
    dev, iast = [], []
    for ln in lines:
        (dev if DEVANAGARI.search(ln) else iast).append(ln)

    def group(pool: list[str]) -> list[list[str]]:
        out, cur = [], []
        for ln in pool:
            cur.append(ln)
            if ln.endswith("||"):
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        return out

    return group(dev), group(iast)


def md_lines(lines: list[str]) -> str:
    """Join physical lines of one verse keeping hard line breaks in Markdown."""
    return "\n".join(ln + "  " if i < len(lines) - 1 else ln for i, ln in enumerate(lines))


def render_hymn(meta: dict, en_title, en_verses, sa_dev, sa_iast) -> str:
    fm = {
        "book": meta["book"],
        "hymn": meta["hymn"],
        "title": meta["title"],
        "translator": "Ralph T.H. Griffith",
        "year": 1896,
        "source_english": meta["en_url"],
        "source_sanskrit": meta["sa_url"],
    }
    parts = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).rstrip(), "---", ""]
    heading = f"# Rig Veda · Book {meta['book']} · Hymn {meta['hymn']}"
    if meta["title"]:
        heading += f" — {meta['title']}"
    parts += [heading, ""]

    parts += ["## English", "", "_tr. Ralph T.H. Griffith [1896]_", ""]
    if en_verses:
        for num, vlines in en_verses:
            parts += [f"### {num}", "", md_lines(vlines), ""]
    else:
        parts += ["_(translation not parsed)_", ""]

    parts += ["## संस्कृतम् (Devanagari)", ""]
    if sa_dev:
        for i, v in enumerate(sa_dev, 1):
            parts += [f"### {i}", "", md_lines(v), ""]
    else:
        parts += ["_(not available)_", ""]

    parts += ["## Transliteration (IAST)", ""]
    if sa_iast:
        for i, v in enumerate(sa_iast, 1):
            parts += [f"### {i}", "", md_lines(v), ""]
    else:
        parts += ["_(not available)_", ""]
    return "\n".join(parts)


def process_hymn(meta: dict) -> dict:
    en_html = fetch(meta["en_url"], "en")
    sa_html = fetch(meta["sa_url"], "sa")
    en_title, en_verses = parse_english(en_html) if en_html else (None, [])
    sa_dev, sa_iast = parse_sanskrit(sa_html) if sa_html else ([], [])
    text = render_hymn(meta, en_title, en_verses, sa_dev, sa_iast)
    book_dir = OUT_ROOT / f"book-{meta['book']:02d}"
    book_dir.mkdir(parents=True, exist_ok=True)
    out = book_dir / f"hymn-{meta['hymn']:03d}.md"
    out.write_text(text, encoding="utf-8")
    return {
        **meta,
        "en_verses": len(en_verses),
        "sa_verses": len(sa_dev),
        "iast_verses": len(sa_iast),
        "ok": bool(en_verses and sa_dev),
    }


def write_readmes(books: dict[int, list[dict]], stats: dict[int, dict]):
    total = sum(s["ok"] for s in stats.values())
    issues = [k for k, s in stats.items() if not s["ok"]]
    lines = [
        "# Rig Veda",
        "",
        "The ten books (maṇḍalas) of the Rig Veda — English translation by",
        "**Ralph T.H. Griffith** [1896], with the Devanagari text and IAST",
        "transliteration.",
        "",
        "> Source: [sacred-texts.com](https://sacred-texts.com/hin/rigveda/index.htm) · Public domain.",
        "",
        "| Book | Hymns |",
        "|-----:|------:|",
    ]
    for b in sorted(books):
        lines.append(f"| [{b}](book-{b:02d}/README.md) | {stats[b]['total']} |")
    lines += ["", f"**Total:** {total} hymns"]
    if issues:
        lines += ["", f"> ⚠ Incomplete parses: {', '.join('B' + str(b) + 'H' + str(b) + '' for b in issues)}"]
    (OUT_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for b, hymns in books.items():
        blines = [
            f"# Rig Veda — Book {b}",
            "",
            f"{len(hymns)} hymns. [← All books](../README.md)",
            "",
            "| Hymn | Title | File |",
            "|------:|-------|------|",
        ]
        for hm in hymns:
            t = hm["title"].replace("|", "\\|")
            blines.append(f"| {hm['hymn']} | {t} | [hymn-{hm['hymn']:03d}.md](hymn-{hm['hymn']:03d}.md) |")
        (OUT_ROOT / f"book-{b:02d}" / "README.md").write_text("\n".join(blines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="1-10", help="e.g. '1-10' or '1,9,10'")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if "-" in args.books:
        lo, hi = args.books.split("-")
        wanted = list(range(int(lo), int(hi) + 1))
    else:
        wanted = [int(x) for x in args.books.split(",")]

    CACHE.mkdir(parents=True, exist_ok=True)
    all_hymns = []
    for b in wanted:
        idx = crawl_book_index(b)
        print(f"Book {b}: {len(idx)} hymns")
        all_hymns.extend(idx)

    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_hymn, hm): hm for hm in all_hymns}
        for fut in as_completed(futures):
            hm = futures[fut]
            try:
                results[(hm["book"], hm["hymn"])] = fut.result()
            except Exception as e:
                print(f"ERROR B{hm['book']}H{hm['hymn']}: {e}", file=sys.stderr)
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(all_hymns)}")

    books: dict[int, list[dict]] = {}
    stats: dict[int, dict] = {}
    for hm in all_hymns:
        books.setdefault(hm["book"], []).append(hm)
    for b, hymns in books.items():
        ok = sum(1 for hm in hymns if results.get((b, hm["hymn"]), {}).get("ok"))
        stats[b] = {"total": len(hymns), "ok": ok}
    write_readmes(books, stats)

    print("\nSummary:")
    for b in sorted(stats):
        s = stats[b]
        flag = "" if s["ok"] == s["total"] else f"  ({s['total'] - s['ok']} incomplete)"
        print(f"  Book {b:>2}: {s['ok']}/{s['total']} ok{flag}")
    bad = [k for k, v in results.items() if not v["ok"]]
    if bad:
        print(f"Incomplete hymns: {sorted(bad)[:20]}{' ...' if len(bad) > 20 else ''}")


if __name__ == "__main__":
    main()
