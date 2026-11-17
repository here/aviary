#!/usr/bin/env python3
"""Fetch Cal-ITP's observed speeds for line 204 and roll them up to our sections.

Caltrans / Cal-ITP publish stop-to-stop bus speeds measured from archived
GTFS-realtime vehicle positions (20th/50th/80th percentile, by time of day).
It is a snapshot of one recent day, refreshed periodically - an independent
check on the timetable-derived series, not a history.

Writes data/reference/calitp_speeds_204.csv
"""
import argparse
import datetime as dt
import json
import pathlib
import urllib.parse
import urllib.request

import pandas as pd

from corridor import LON_TOLERANCE, SECTIONS, VERMONT_LON

LAYER = "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHrailroad/Speeds_by_Stop_Segments/FeatureServer/0/query"
# Cal-ITP time-of-day bins, as local clock hours [start, end)
PERIOD_HOURS = {"Owl": (0, 4), "Early AM": (4, 7), "AM Peak": (7, 10), "Midday": (10, 15), "PM Peak": (15, 20), "Evening": (20, 24)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/reference"))
    a = ap.parse_args()
    q = urllib.parse.urlencode({"where": "route_name='204' AND agency LIKE 'Los Angeles County Metro%'",
                                "outFields": "*", "outSR": 4326, "f": "json"})
    feats = json.load(urllib.request.urlopen(f"{LAYER}?{q}", timeout=120))["features"]
    rows = []
    for f in feats:
        at, pts = f["attributes"], [p for path in (f.get("geometry") or {}).get("paths", []) for p in path]
        if not pts:
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lats = [p[1] for p in pts]
        if abs(lon - VERMONT_LON) > LON_TOLERANCE or not at["p50_mph"]:
            continue
        rows.append({"time_period": at["time_period"], "direction": "northbound" if at["direction_id"] == 0 else "southbound",
                     "mid_lat": (max(lats) + min(lats)) / 2, "miles": at["Shape__Length"] / 1609.34,
                     "p20": at["p20_mph"], "p50": at["p50_mph"], "p80": at["p80_mph"], "n_trips": at["n_trips"]})
    df = pd.DataFrame(rows)
    df["section_id"] = None
    for s in SECTIONS:
        df.loc[(df.mid_lat <= s["north_lat"]) & (df.mid_lat > s["south_lat"]), "section_id"] = s["section_id"]
    df = df.dropna(subset=["section_id"])
    both = pd.concat([df, df.assign(section_id="corridor")])
    for c in ("p20", "p50", "p80"):  # distance-weighted harmonic mean = speed over the whole stretch
        both[f"h_{c}"] = both.miles / both[c]
    g = both.groupby(["section_id", "direction", "time_period"])
    out = pd.DataFrame({"p20_mph": g.miles.sum() / g.h_p20.sum(), "p50_mph": g.miles.sum() / g.h_p50.sum(),
                        "p80_mph": g.miles.sum() / g.h_p80.sum(), "median_n_trips": g.n_trips.median(),
                        "n_segments": g.size()}).round(2).reset_index()
    out["start_hour"] = out.time_period.map(lambda p: PERIOD_HOURS[p][0])
    out["end_hour"] = out.time_period.map(lambda p: PERIOD_HOURS[p][1])
    out["route"], out["source"], out["retrieved"] = "204", "calitp_speeds_by_stop_segments", dt.date.today().isoformat()
    a.out.mkdir(parents=True, exist_ok=True)
    out.sort_values(["section_id", "direction", "start_hour"]).to_csv(a.out / "calitp_speeds_204.csv", index=False)
    print(out[out.section_id == "corridor"].to_string(index=False))
