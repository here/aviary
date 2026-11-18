#!/usr/bin/env python3
"""Measured bus speed history from Cal-ITP's public speed maps, rolled up to our street sections.

Cal-ITP (Caltrans) publishes the speed maps from its realtime analysis in a public Google Cloud Storage bucket,
`calitp-map-tiles`, one folder per analysis day (`segment_speeds_YYYY-MM-DD/`, roughly monthly, Wednesdays, since
October 2024). Each LA Metro file holds every stop-to-stop segment of every bus line for one time of day, with
measured 20th / 50th / 80th percentile speeds and a polygon for the segment.

LA Metro's bus feed appears under three names over time: an internal record id (`recPnGkwdpnr8jmHB`, then
`recX8JOPmBQM9aWLC`) and the base64 of its GTFS address. Only `new_speedmap` files are used; `_CC` variants and
`excluded_shapes` / `speed_variation` files are skipped.

    python pipeline/fetch_calitp_history.py                 # downloads into run/calitp/ (cached), writes CSVs

Writes, per street, one row per analysis date, time of day, line, direction and section:
    data/calitp/vermont_calitp_history.csv
    data/corridors/<id>/calitp/<id>_calitp_history.csv

Matching: each segment's two stops are located on the street's path from LA Metro's current GTFS stops (direction
comes from their order); a segment counts when both stops lie within MAX_OFFSET_MI of the path. A section's speed
is distance over summed travel time of the segments overlapping it (harmonic), separately for p20, p50 and p80.
"""
import argparse
import base64
import csv
import gzip
import io
import json
import pathlib
import re
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict

import numpy as np

from build_traffic import VERMONT
from polyline import PolylineCorridor

BUCKET = "https://storage.googleapis.com/storage/v1/b/calitp-map-tiles/o"
GTFS_URL = "https://gitlab.com/LACMTA/gtfs_bus/raw/master/gtfs_bus.zip"
LA_KEYS = ["recPnGkwdpnr8jmHB", "recX8JOPmBQM9aWLC", base64.b64encode(GTFS_URL.encode()).decode()]
MAX_OFFSET_MI = 0.04     # about 65 m: stop poles sit at the curb, sometimes around a corner
MIN_COVERAGE = 0.5
PERIOD_HOURS = {"Owl": "0-4", "Early AM": "4-7", "AM Peak": "7-10", "Midday": "10-15", "PM Peak": "15-20", "Evening": "20-24", "All day": "0-24"}
FIELDS = ["corridor_id", "analysis_date", "period", "hours", "route", "direction", "section_id", "p20_mph", "p50_mph",
          "p80_mph", "length_mi", "coverage", "n_trips", "source"]


def get(url: str, headers=None) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aviary/1.0", **(headers or {})}), timeout=180).read()


def inventory() -> list[dict]:
    top = json.loads(get(BUCKET + "?delimiter=/&maxResults=1000"))["prefixes"]
    out = []
    for snap in [p for p in top if p.startswith("segment_speeds_")]:
        tok = None
        while True:
            q = {"prefix": snap, "maxResults": 1000, **({"pageToken": tok} if tok else {})}
            d = json.loads(get(BUCKET + "?" + urllib.parse.urlencode(q)))
            for o in d.get("items", []):
                n = o["name"]
                m = re.search(r"new_speedmap(?:_(.*?))?\.geojson", n)
                if m and any(k in n for k in LA_KEYS) and not (m.group(1) or "").endswith("_CC"):
                    out.append({"name": n, "date": n.split("/")[1][:10], "period": m.group(1) or "All day", "bytes": int(o["size"])})
            tok = d.get("nextPageToken")
            if not tok:
                break
    # one file per (analysis date, period); some folders repeat earlier dates
    best = {}
    for x in out:
        best.setdefault((x["date"], x["period"]), x)
    return sorted(best.values(), key=lambda x: (x["date"], x["period"]))


def load_geojson(item: dict, cache: pathlib.Path) -> dict:
    path = cache / item["name"].replace("/", "__").replace(" ", "_")
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(get(BUCKET + "/" + urllib.parse.quote(item["name"], safe="") + "?alt=media"))
    raw = path.read_bytes()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    return json.loads(raw)


def stops(cache: pathlib.Path) -> dict[str, tuple[float, float]]:
    path = cache / "gtfs_bus.zip"
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(get(GTFS_URL))
    with zipfile.ZipFile(path) as z:
        rows = csv.DictReader(io.TextIOWrapper(z.open("stops.txt"), encoding="utf-8-sig"))
        return {r["stop_id"]: (float(r["stop_lat"]), float(r["stop_lon"])) for r in rows}


def harmonic(parts, key):
    p = [(m, s[key]) for m, s in parts if s.get(key)]
    return round(sum(m for m, _ in p) / sum(m / v for m, v in p), 2) if p else ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=pathlib.Path, default=pathlib.Path("run/calitp"))
    a = ap.parse_args()
    streets = [(PolylineCorridor(VERMONT), pathlib.Path("data/calitp") / "vermont_calitp_history.csv")]
    for path in sorted(pathlib.Path("corridors").glob("*.json")):
        cfg = json.loads(path.read_text())
        if cfg.get("routes"):
            streets.append((PolylineCorridor(cfg), pathlib.Path("data/corridors") / cfg["corridor_id"] / "calitp" / f"{cfg['corridor_id']}_calitp_history.csv"))
    stop_ll = stops(a.cache)
    items = inventory()
    print(f"{len(items)} LA Metro speed maps, {sum(i['bytes'] for i in items) // 1_000_000} MB")

    rows = {str(o): [] for _, o in streets}
    for item in items:
        feats = load_geojson(item, a.cache)["features"]
        for c, out in streets:
            per = defaultdict(list)  # (route, direction, section) -> [(miles, props)]
            for f in feats:
                p = f["properties"]
                route = str(p.get("route_short_name") or str(p.get("route_id", "")).split("-")[0])
                if route not in c.routes:
                    continue
                ids = str(p.get("stop_pair", "")).split("__")
                if len(ids) != 2 or ids[0] not in stop_ll or ids[1] not in stop_ll:
                    continue
                lat = np.array([stop_ll[ids[0]][0], stop_ll[ids[1]][0]])
                lon = np.array([stop_ll[ids[0]][1], stop_ll[ids[1]][1]])
                s, off = c.locate(lat, lon)
                if off.max() > MAX_OFFSET_MI or s[0] == s[1]:
                    continue
                direction = c.dir_up if s[1] > s[0] else c.dir_down
                lo, hi = sorted(map(float, s))
                for sec in c.sections:
                    overlap = min(hi, sec["end_mi"]) - max(lo, sec["start_mi"])
                    if overlap > 0:
                        per[(route, direction, sec["section_id"])].append((overlap, p))
            for (route, direction, sid), parts in per.items():
                length = next(x["length_mi"] for x in c.sections if x["section_id"] == sid)
                coverage = min(sum(m for m, _ in parts) / length, 1.0)
                if coverage < MIN_COVERAGE:
                    continue
                rows[str(out)].append({
                    "corridor_id": c.id, "analysis_date": item["date"], "period": item["period"], "hours": PERIOD_HOURS.get(item["period"], ""),
                    "route": route, "direction": direction, "section_id": sid,
                    "p20_mph": harmonic(parts, "p20_mph"), "p50_mph": harmonic(parts, "p50_mph"), "p80_mph": harmonic(parts, "p80_mph"),
                    "length_mi": length, "coverage": round(coverage, 3), "n_trips": min(int(pp.get("n_trips") or 0) for _, pp in parts),
                    "source": "calitp_segment_speeds"})
        print(f"  {item['date']} {item['period']:9} {len(feats):6} segments")

    for c, out in streets:
        r = sorted(rows[str(out)], key=lambda x: (x["analysis_date"], x["period"], x["route"], x["direction"], x["section_id"]))
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(r)
        print(f"{c.id}: {len(r)} rows, {len({x['analysis_date'] for x in r})} dates -> {out}")


if __name__ == "__main__":
    main()
