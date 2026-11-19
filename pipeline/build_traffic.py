#!/usr/bin/env python3
"""Hourly general-traffic speeds per street section, from archived TomTom or HERE traffic flow.

The traffic Worker stores two providers in R2:
- TomTom Orbis Maps Traffic API v2 Vector Flow Tiles every 15 minutes under traffic/tomtom/ (one gzipped JSON per
  run, tiles base64-encoded);
- HERE Traffic API v7 flow every 90 minutes under traffic/here/, one gzipped response per street, requested with
  the corridor filter along that street's path (file name here_<corridor_id>_<YYYY-MM-DDTHHMM>.json.gz).
This keeps the road pieces that run along each study street and writes, per hour, section and direction:

    TomTom:  data/traffic/vermont_traffic_YYYY-MM.csv, data/corridors/<id>/traffic/<id>_traffic_YYYY-MM.csv
    HERE:    data/traffic/vermont_here_traffic_YYYY-MM.csv, data/corridors/<id>/traffic/<id>_here_traffic_YYYY-MM.csv

    python pipeline/build_traffic.py --raw run/traffic/tomtom
    python pipeline/build_traffic.py --provider here --raw run/traffic/here

HERE specifics: each flow item lists its road as map links in driving direction; every link is matched as a piece,
with the item's speed (or the sub-segment's, when HERE splits an item). Links whose confidence is 0.7 or lower are
left out, because HERE marks those as historical speeds or the speed limit rather than live traffic. A HERE file is
matched only to its own street, so roads that the corridor filter returns near intersections cannot leak into
another street's rows.

Method
- A road piece belongs to a street when every point of it lies within MAX_OFFSET_MI of the street's path and it
  runs along the path (distance gained along the path is at least ALONG_SHARE of the piece's own length), which
  keeps cross streets out. Its direction comes from the order of its points.
- Within one snapshot, a section's speed is covered length divided by the summed travel time of its pieces
  (time = length / speed), so slow pieces weigh as they do for a driver. Free-flow speed uses each piece's speed
  divided by its relative speed. Pieces reported closed, or at 0 km/h, are counted in `closed_share` and left out
  of the speed.
- The hourly value averages the snapshots in that hour by travel time (harmonic mean of speeds). The whole-street
  row (`section_id = corridor`) sums section travel times in each snapshot where every section has a speed.
- Files merge: an hour that is processed again replaces the earlier row.
"""
import argparse
import base64
import gzip
import json
import math
import pathlib
from collections import defaultdict

import numpy as np
import pandas as pd

from corridor import BREAKPOINTS, TIMEZONE
from mvt import decode
from polyline import PolylineCorridor

MAX_OFFSET_MI = 0.025   # about 40 m (Vermont is a wide divided road south of Manchester Av)
ALONG_SHARE = 0.8
MIN_COVERAGE = 0.5      # a section needs at least half its length covered in a snapshot
KMH_TO_MPH = 0.621371
KEYS = ["hour_start_utc", "direction", "section_id"]
SOURCES = {"tomtom": "tomtom_traffic_flow", "here": "here_traffic_flow"}
MPS_TO_MPH = 2.236936
HERE_MIN_CONFIDENCE = 0.7   # above this HERE reports live (probe) speeds; at or below, historical or speed limit

# Vermont Av as a path, north to south so its sections keep the ids used everywhere else (S1 = Sunset to Wilshire).
VERMONT = {
    "corridor_id": "vermont", "name": "Vermont Av, Sunset Bl to Athens Station", "routes": ["204", "754"],
    "directions": {"increasing": "southbound", "decreasing": "northbound"},
    "breakpoints": [[name, -118.2914, lat] for name, lat in BREAKPOINTS],
    "line": [[-118.2919, 34.1010], [-118.2917, 33.9235]],  # road centre; the divided south end runs at about -118.2917
}


def corridors() -> list[tuple[PolylineCorridor, pathlib.Path]]:
    out = [(PolylineCorridor(VERMONT), pathlib.Path("data/traffic"))]
    for path in sorted(pathlib.Path("corridors").glob("*.json")):
        cfg = json.loads(path.read_text())
        out.append((PolylineCorridor(cfg), pathlib.Path("data/corridors") / cfg["corridor_id"] / "traffic"))
    return out


def tile_lonlat(z: int, x: int, y: int, extent: int, px: float, py: float) -> tuple[float, float]:
    n = 2 ** z
    lon = (x + px / extent) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / extent) / n))))
    return lon, lat


def tomtom_pieces(run: dict):
    """Yield (lons, lats, mph, free_mph, closed) for every road piece in one stored TomTom run.

    Pieces on a tile border can appear in both tiles; identical ones are yielded once.
    """
    seen = set()
    for key, b64 in run["tiles"].items():
        z, x, y = map(int, key.split("/"))
        layer = decode(base64.b64decode(b64)).get("Traffic flow")
        if not layer:
            continue
        for f in layer["features"]:
            for part in f["geometry"]:
                if len(part) >= 2:
                    ll = [tile_lonlat(z, x, y, layer["extent"], px, py) for px, py in part]
                    sig = (f["properties"].get("openlr"), tuple((round(lo, 5), round(la, 5)) for lo, la in ll))
                    if sig in seen:
                        continue
                    seen.add(sig)
                    props = f["properties"]
                    kmh, rel = props.get("absolute_speed"), props.get("relative_speed")
                    mph = (kmh or 0) * KMH_TO_MPH
                    free = mph / rel if rel and rel > 0 and mph > 0 else None
                    closed = bool(props.get("road_closure")) or not kmh
                    yield np.array([p[0] for p in ll]), np.array([p[1] for p in ll]), mph, free, closed


def here_pieces(resp: dict):
    """Yield (lons, lats, mph, free_mph, closed) for every map link in one HERE flow response."""
    for item in resp.get("results", []):
        cf = item.get("currentFlow") or {}
        links = (item.get("location", {}).get("shape") or {}).get("links") or []
        subs = cf.get("subSegments") or []
        bounds = np.cumsum([s.get("length", 0) for s in subs]) if subs else None
        pos = 0.0
        for link in links:
            mid, pos = pos + link.get("length", 0) / 2, pos + link.get("length", 0)
            flow = subs[min(int(np.searchsorted(bounds, mid)), len(subs) - 1)] if subs else cf
            pts = link.get("points") or []
            if len(pts) < 2:
                continue
            conf = flow.get("confidence", cf.get("confidence"))
            closed = flow.get("traversability") == "closed" or flow.get("jamFactor") == 10
            if not closed and (conf is None or conf <= HERE_MIN_CONFIDENCE or not flow.get("speed")):
                continue
            mph = (flow.get("speed") or 0) * MPS_TO_MPH
            free = flow["freeFlow"] * MPS_TO_MPH if flow.get("freeFlow") else None
            yield np.array([p["lng"] for p in pts]), np.array([p["lat"] for p in pts]), mph, free, closed


def snapshot(pieces, streets, only=None) -> list[dict]:
    """Section speeds for one run. `pieces` yields (lons, lats, mph, free_mph, closed); `only` limits to street indexes."""
    per = defaultdict(list)  # (corridor index, direction, section_id) -> [(miles, mph, free_mph, closed)]
    for lons, lats, mph, free, closed in pieces:
        for ci, (c, _) in enumerate(streets):
            if only is not None and ci not in only:
                continue
            s, off = c.locate(lats, lons)
            if off.max() > MAX_OFFSET_MI:
                continue
            xy = c._plane(lons, lats)
            own = float(np.hypot(*np.diff(xy, axis=0).T).sum())
            if own <= 0 or abs(s[-1] - s[0]) < ALONG_SHARE * own:
                continue
            direction = c.dir_up if s[-1] > s[0] else c.dir_down
            lo, hi = sorted((float(s[0]), float(s[-1])))
            for sec in c.sections:
                overlap = min(hi, sec["end_mi"]) - max(lo, sec["start_mi"])
                if overlap > 0:
                    per[(ci, direction, sec["section_id"])].append((overlap, mph, free, closed))
    rows = []
    for (ci, direction, sid), parts in per.items():
        c = streets[ci][0]
        length = next(x["length_mi"] for x in c.sections if x["section_id"] == sid)
        covered = min(sum(p[0] for p in parts), length)
        moving = [p for p in parts if not p[3] and p[1] > 0]
        closed_len = sum(p[0] for p in parts if p[3])
        row = {"ci": ci, "direction": direction, "section_id": sid, "length_mi": length,
               "coverage": covered / length, "closed_share": closed_len / covered if covered else 0.0, "mph": None, "free_mph": None}
        if moving and covered / length >= MIN_COVERAGE:
            row["mph"] = sum(p[0] for p in moving) / sum(p[0] / p[1] for p in moving)
            ff = [p for p in moving if p[2]]
            if ff:
                row["free_mph"] = sum(p[0] for p in ff) / sum(p[0] / p[2] for p in ff)
        rows.append(row)
    return rows


def harmonic(values) -> float | None:
    v = [x for x in values if x and x > 0]
    return len(v) / sum(1 / x for x in v) if v else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", choices=["tomtom", "here"], default="tomtom")
    ap.add_argument("--raw", type=pathlib.Path, help="searched recursively (default run/traffic/<provider>)")
    a = ap.parse_args()
    raw = a.raw or pathlib.Path("run/traffic") / a.provider
    streets = corridors()
    index = {c.id: i for i, (c, _) in enumerate(streets)}
    files = sorted(raw.rglob("tomtom_flow_*.json.gz" if a.provider == "tomtom" else "here_*_*.json.gz"))
    if not files:
        raise SystemExit(f"no {a.provider} runs found under {raw}")

    snaps = []
    for path in files:
        try:
            data = json.loads(gzip.open(path).read())
        except Exception as exc:  # one damaged file should not stop the rest
            print(f"skipped {path.name}: {exc!r}")
            continue
        if a.provider == "tomtom":
            at, rows = pd.Timestamp(data["at"]), snapshot(tomtom_pieces(data), streets)
        else:
            cid, stamp = path.name[len("here_"):-len(".json.gz")].rsplit("_", 1)
            if cid not in index:
                continue
            at = pd.Timestamp(stamp[:13] + ":" + stamp[13:], tz="UTC")
            rows = snapshot(here_pieces(data), streets, only={index[cid]})
        for r in rows:
            r["at"] = at
            snaps.append(r)
    if not snaps:
        raise SystemExit("no road pieces matched any street")
    df = pd.DataFrame(snaps)
    df["hour"] = df["at"].dt.floor("h")

    # Whole-street rows per snapshot: sum of section travel times when every section has a speed.
    whole = []
    for (ci, direction, at), g in df.groupby(["ci", "direction", "at"]):
        c = streets[ci][0]
        if len(g.dropna(subset=["mph"])) == len(c.sections):
            minutes = (g.length_mi / g.mph * 60).sum()
            free_min = (g.length_mi / g.free_mph * 60).sum() if g.free_mph.notna().all() else None
            whole.append({"ci": ci, "direction": direction, "section_id": "corridor", "length_mi": c.total["length_mi"],
                          "coverage": g.coverage.mean(), "closed_share": g.closed_share.mean(),
                          "mph": c.total["length_mi"] / (minutes / 60),
                          "free_mph": c.total["length_mi"] / (free_min / 60) if free_min else None, "at": at, "hour": at.floor("h")})
    if whole:
        df = pd.concat([df, pd.DataFrame(whole)], ignore_index=True)

    written = 0
    for ci, (c, out_dir) in enumerate(streets):
        g = df[df.ci == ci]
        if g.empty:
            print(f"{c.id}: no matching road pieces")
            continue
        h = g.groupby(["hour", "direction", "section_id"]).agg(
            length_mi=("length_mi", "first"), mph=("mph", harmonic), free_mph=("free_mph", harmonic),
            coverage=("coverage", "mean"), closed_share=("closed_share", "mean"), n_snapshots=("at", "nunique")).reset_index()
        h[["mph", "free_mph"]] = h[["mph", "free_mph"]].apply(pd.to_numeric)  # all-missing columns come back as objects
        h["corridor_id"] = c.id
        h["hour_start_utc"] = h.hour.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        h["hour_start_local"] = h.hour.dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        h["speed_mph"] = h.mph.round(2)
        h["free_flow_mph"] = h.free_mph.round(2)
        h["travel_time_min"] = (h.length_mi / h.mph * 60).round(2)
        h[["coverage", "closed_share"]] = h[["coverage", "closed_share"]].round(3)
        h["source"] = SOURCES[a.provider]
        h = h[["corridor_id", "hour_start_utc", "hour_start_local", "direction", "section_id", "speed_mph", "free_flow_mph",
               "travel_time_min", "length_mi", "coverage", "closed_share", "n_snapshots", "source"]]
        out_dir.mkdir(parents=True, exist_ok=True)
        for month, m in h.groupby(h.hour_start_local.str[:7]):
            target = out_dir / (f"{c.id}_traffic_{month}.csv" if a.provider == "tomtom" else f"{c.id}_here_traffic_{month}.csv")
            if target.exists():
                m = pd.concat([pd.read_csv(target, dtype=str, keep_default_na=False), m.astype(str).replace("nan", "")]).drop_duplicates(KEYS, keep="last")
            m.sort_values(KEYS).to_csv(target, index=False)
        covered = h[h.section_id != "corridor"].groupby("section_id").coverage.mean()
        print(f"{c.id}: {len(h)} hourly rows, {h.section_id.nunique()} sections; mean coverage {covered.mean():.0%}")
        written += len(h)
    print(f"{len(files)} runs -> {written} hourly rows")


if __name__ == "__main__":
    main()
