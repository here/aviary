#!/usr/bin/env python3
"""Pull hourly Telraam counts for the road segments listed in corridors/*.json.

UNTESTED: written before the project had a Telraam API key. The endpoint and field names follow Telraam's public
API v1 as documented on Postman (https://documenter.gw.postman.com/view/metadata/TWDRqyaV); check them on the first
real run and fix this docstring once confirmed.

A street opts in by listing its segments:
    "telraam_segments": [{"id": 9000001234, "section_id": "S2", "label": "Sunset Bl by the Vista Theatre"}]

    TELRAAM_API_KEY=... python pipeline/fetch_telraam.py --days 3

Writes data/corridors/<id>/telraam/<id>_telraam_YYYY-MM.csv (one file per local month), replacing any hour that is
fetched again. Counts are both directions combined, as Telraam reports at segment level.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import urllib.request

import pandas as pd

from corridor import TIMEZONE

API = "https://telraam-api.net/v1/reports/traffic"
KEEP = ["date", "uptime", "pedestrian", "bike", "car", "heavy", "v85"]


def fetch(segment_id: int, start: dt.datetime, end: dt.datetime, key: str) -> list[dict]:
    body = json.dumps({"level": "segments", "format": "per-hour", "id": str(segment_id),
                       "time_start": start.strftime("%Y-%m-%d %H:%M:%SZ"), "time_end": end.strftime("%Y-%m-%d %H:%M:%SZ")}).encode()
    req = urllib.request.Request(API, data=body, method="POST",
                                 headers={"X-Api-Key": key, "Content-Type": "application/json", "User-Agent": "aviary-telraam/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("report", [])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=3, help="how many days back to fetch")
    ap.add_argument("--corridors", type=pathlib.Path, default=pathlib.Path("corridors"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/corridors"))
    a = ap.parse_args()
    key = os.environ.get("TELRAAM_API_KEY", "")
    if not key:
        raise SystemExit("TELRAAM_API_KEY is not set; nothing to do")
    end = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - dt.timedelta(days=a.days)

    for path in sorted(a.corridors.glob("*.json")):
        cfg = json.loads(path.read_text())
        segs = cfg.get("telraam_segments", [])
        if not segs:
            continue
        rows = []
        for s in segs:
            for r in fetch(s["id"], start, end, key):
                rows.append({"corridor_id": cfg["corridor_id"], "telraam_segment": s["id"], "section_id": s.get("section_id", ""),
                             **{k: r.get(k) for k in KEEP}})
        if not rows:
            print(f"{cfg['corridor_id']}: no Telraam rows")
            continue
        df = pd.DataFrame(rows)
        t = pd.to_datetime(df.pop("date"), utc=True)
        df.insert(1, "hour_start_utc", t.dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
        df.insert(2, "hour_start_local", t.dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%dT%H:%M:%S%z"))
        out = a.out / cfg["corridor_id"] / "telraam"
        out.mkdir(parents=True, exist_ok=True)
        keys = ["hour_start_utc", "telraam_segment"]
        for month, g in df.groupby(df.hour_start_local.str[:7]):
            target = out / f"{cfg['corridor_id']}_telraam_{month}.csv"
            if target.exists():
                g = pd.concat([pd.read_csv(target, dtype=str), g.astype(str)]).drop_duplicates(keys, keep="last")
            g.sort_values(keys).to_csv(target, index=False)
        print(f"{cfg['corridor_id']}: {len(df)} hourly rows from {len(segs)} segment(s)")


if __name__ == "__main__":
    main()
