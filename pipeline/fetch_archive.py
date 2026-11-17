#!/usr/bin/env python3
"""Download archived files from the project's public API (no keys needed).

    python pipeline/fetch_archive.py --prefix raw/2026-11-17/ --out run/raw

Prefixes: raw/ (minute files, kept 7 days), daily/, mds/, gbfs/.
"""
import argparse
import json
import pathlib
import urllib.parse
import urllib.request

UA = {"User-Agent": "aviary-fetch/1.0"}  # the default Python agent is refused


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="https://aviary.herebox.org")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("run"))
    a = ap.parse_args()
    cursor, n = None, 0
    while True:
        q = {"prefix": a.prefix, **({"cursor": cursor} if cursor else {})}
        page = json.loads(get(f"{a.base}/api/files?{urllib.parse.urlencode(q)}"))
        for f in page["files"]:
            target = a.out / f["key"]
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(get(a.base + urllib.parse.quote(f["url"])))
                n += 1
        cursor = page.get("next_cursor")
        if not cursor:
            break
    print(f"downloaded {n} new files under {a.out}")
