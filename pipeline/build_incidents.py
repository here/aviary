#!/usr/bin/env python3
"""Traffic incidents per street section, from archived TomTom Incident Details polls.

The traffic Worker polls TomTom Traffic API v5 Incident Details every 20 minutes for one box over all study streets
and stores each response under traffic/incidents/ (one gzipped JSON per poll: {"at", "box", "response"}). This keeps
the incidents whose line runs along a study street, splits them by section, and keeps one row per incident, section
and direction, with the first and last time it was seen:

    data/incidents/vermont_incidents_YYYY.csv
    data/corridors/<id>/incidents/<id>_incidents_YYYY.csv

    python pipeline/build_incidents.py --raw run/traffic/incidents

Matching: the points of an incident's line that lie within MAX_OFFSET_MI of the street's path are kept; the kept part
must be at least MIN_LENGTH_MI long and run along the path (as for traffic pieces), which leaves out cross streets.
Direction comes from the order of the points. Files merge: re-processing a poll widens first/last seen and keeps the
largest delay, so running over overlapping windows is safe. Rows are filed by the year the incident was first seen.
"""
import argparse
import gzip
import json
import pathlib
from collections import defaultdict

import numpy as np
import pandas as pd

from build_traffic import ALONG_SHARE, MAX_OFFSET_MI, corridors
from corridor import TIMEZONE

MIN_LENGTH_MI = 0.02     # about 30 m on the street
SOURCE = "tomtom_incident_details"
KEYS = ["incident_id", "section_id", "direction"]
CATEGORY = {0: "unknown", 1: "accident", 2: "fog", 3: "dangerous conditions", 4: "rain", 5: "ice", 6: "jam",
            7: "lane closed", 8: "road closed", 9: "road works", 10: "wind", 11: "flooding", 14: "broken down vehicle"}
FIELDS = ["corridor_id", "incident_id", "section_id", "direction", "category", "description", "magnitude",
          "max_delay_s", "start_time_utc", "end_time_utc", "first_seen_utc", "last_seen_utc", "from_street",
          "to_street", "length_on_section_mi", "source"]


def match(coords, c):
    """Return [(section_id, direction, miles on section)] for one incident line on one street, or []."""
    pts = np.array(coords, dtype=float)
    if pts.ndim != 2 or len(pts) < 2:
        return []
    s, off = c.locate(pts[:, 1], pts[:, 0])
    keep = off <= MAX_OFFSET_MI
    if keep.sum() < 2:
        return []
    s_k, xy = s[keep], c._plane(pts[keep, 0], pts[keep, 1])
    own = float(np.hypot(*np.diff(xy, axis=0).T).sum())
    gained = abs(float(s_k[-1] - s_k[0]))
    if gained < MIN_LENGTH_MI or own <= 0 or gained < ALONG_SHARE * own:
        return []
    direction = c.dir_up if s_k[-1] > s_k[0] else c.dir_down
    lo, hi = sorted((float(s_k[0]), float(s_k[-1])))
    out = []
    for sec in c.sections:
        overlap = min(hi, sec["end_mi"]) - max(lo, sec["start_mi"])
        if overlap > 0:
            out.append((sec["section_id"], direction, overlap))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", type=pathlib.Path, default=pathlib.Path("run/traffic/incidents"), help="searched recursively")
    a = ap.parse_args()
    streets = corridors()
    files = sorted(a.raw.rglob("tomtom_incidents_*.json.gz"))
    if not files:
        raise SystemExit(f"no incident polls under {a.raw}")

    rows = defaultdict(dict)  # (street index, incident, section, direction) -> row
    for path in files:
        try:
            poll = json.loads(gzip.open(path).read())
        except Exception as exc:
            print(f"skipped {path.name}: {exc!r}")
            continue
        at = pd.Timestamp(poll["at"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        for inc in poll.get("response", {}).get("incidents", []):
            p, g = inc.get("properties", {}), inc.get("geometry", {})
            coords = g.get("coordinates") if g.get("type") == "LineString" else None
            if not coords:
                continue
            for ci, (c, _) in enumerate(streets):
                for sid, direction, miles in match(coords, c):
                    k = (ci, p.get("id"), sid, direction)
                    r = rows[k]
                    cat = p.get("iconCategory")
                    events = "; ".join(e.get("description", "") for e in p.get("events") or [] if e.get("description"))
                    r.update({
                        "corridor_id": c.id, "incident_id": p.get("id"), "section_id": sid, "direction": direction,
                        "category": CATEGORY.get(cat, str(cat)), "description": events, "magnitude": p.get("magnitudeOfDelay"),
                        "max_delay_s": max(filter(None, [r.get("max_delay_s"), p.get("delay")]), default=None),
                        "start_time_utc": p.get("startTime"), "end_time_utc": p.get("endTime"),
                        "first_seen_utc": min(filter(None, [r.get("first_seen_utc"), at])),
                        "last_seen_utc": max(filter(None, [r.get("last_seen_utc"), at])),
                        "from_street": p.get("from"), "to_street": p.get("to"),
                        "length_on_section_mi": round(miles, 3), "source": SOURCE})

    written = 0
    for ci, (c, traffic_dir) in enumerate(streets):
        new = pd.DataFrame([r for (i, *_), r in rows.items() if i == ci], columns=FIELDS)
        out_dir = traffic_dir.parent / "incidents"
        existing = sorted(out_dir.glob(f"{c.id}_incidents_*.csv"))
        if new.empty and not existing:
            continue
        old = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in existing]) if existing else pd.DataFrame(columns=FIELDS)
        both = pd.concat([old, new.astype(str).replace({"None": "", "nan": ""})], ignore_index=True)
        both["max_delay_s"] = pd.to_numeric(both.max_delay_s, errors="coerce")
        merged = both.groupby(KEYS, as_index=False).agg(
            **{f: (f, "last") for f in FIELDS if f not in KEYS + ["first_seen_utc", "last_seen_utc", "max_delay_s"]},
            first_seen_utc=("first_seen_utc", lambda v: min(x for x in v if x)),
            last_seen_utc=("last_seen_utc", lambda v: max(x for x in v if x)),
            max_delay_s=("max_delay_s", "max"))[FIELDS]
        merged["max_delay_s"] = merged.max_delay_s.map(lambda v: "" if pd.isna(v) else str(int(v)))
        year = pd.to_datetime(merged.first_seen_utc, utc=True).dt.tz_convert(TIMEZONE).dt.year
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in existing:
            f.unlink()
        for y, g in merged.groupby(year):
            g.sort_values(["first_seen_utc", "incident_id", "section_id"]).to_csv(out_dir / f"{c.id}_incidents_{y}.csv", index=False)
        kinds = new.category.value_counts().to_dict() if not new.empty else {}
        print(f"{c.id}: {len(merged)} incident-section rows ({len(new)} from these polls) {kinds}")
        written += len(new)
    print(f"{len(files)} polls -> {written} incident-section rows")


if __name__ == "__main__":
    main()
