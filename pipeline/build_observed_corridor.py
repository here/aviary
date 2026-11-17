#!/usr/bin/env python3
"""Measured bus speeds for a path-based corridor, including its short focus segments.

Reads raw vehicle positions (as written by the collectors) and writes, under
data/corridors/<id>/observed/:

    <id>_observed_YYYY-MM.csv           hourly speed per section (same columns as the schedule archive)
    <id>_focus_traversals_YYYY-MM.csv   one row per bus passing through a focus segment
    <id>_focus_hourly_YYYY-MM.csv       per hour: trips, median seconds, 20th/80th percentile, speed

    python pipeline/fetch_archive.py --prefix raw/2026-11-17/ --out run
    python pipeline/build_observed_corridor.py --corridor corridors/sunset.json --raw run/raw

Sections use the same method as build_observed.py: distance gained between consecutive pings
divided by the time between them, summed over the hour. Focus segments are too short for that
to be stable, so each bus is timed across the segment: the moment it crosses each end is
interpolated between the two pings either side.
"""
import argparse
import pathlib

import numpy as np
import pandas as pd

from build_observed import MAX_GAP_S, MAX_SPEED_MPH, MIN_COVERAGE, load
from corridor import TIMEZONE
from polyline import ON_LINE_MI, PolylineCorridor

CROSS_GAP_S = 120          # the two pings either side of a boundary must be this close together
MAX_TRAVERSE_S = 1800
SECTION_KEYS = ["hour_start_utc", "route", "direction", "section_id"]
TRAVERSAL_KEYS = ["focus_id", "vehicle_id", "trip_id", "entered_utc"]


def locate(pings: pd.DataFrame, c: PolylineCorridor) -> pd.DataFrame:
    p = pings[pings.route.isin(c.routes)].copy()
    p["s"], off = c.locate(p.lat.to_numpy(), p.lon.to_numpy())
    return p[off < ON_LINE_MI].sort_values(["vehicle_id", "trip_id", "ts"])


def local_iso(utc: pd.Series) -> pd.Series:
    return utc.dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def hourly_sections(p: pd.DataFrame, c: PolylineCorridor) -> pd.DataFrame:
    g = p.groupby(["vehicle_id", "trip_id"], sort=False)
    x = p.assign(dt=g.ts.diff(), ds=g.s.diff(), mid_s=(p.s + g.s.shift()) / 2, mid_ts=(p.ts + g.ts.shift()) / 2)
    x = x[(x.dt > 0) & (x.dt <= MAX_GAP_S)].copy()
    net = g.s.agg(lambda v: v.iloc[-1] - v.iloc[0]).rename("net").reset_index()
    x = x.merge(net, on=["vehicle_id", "trip_id"])
    x = x[x.net != 0]
    up = x.net > 0
    x["direction"] = np.where(up, c.dir_up, c.dir_down)
    x["miles"] = x.ds * np.where(up, 1, -1)
    x = x[(x.miles / (x.dt / 3600)).abs() <= MAX_SPEED_MPH]
    x["section_id"] = None
    for s in c.sections:
        x.loc[(x.mid_s >= s["start_mi"]) & (x.mid_s < s["end_mi"]), "section_id"] = s["section_id"]
    x = x.dropna(subset=["section_id"])
    x["hour_start_utc"] = pd.to_datetime(x.mid_ts, unit="s", utc=True).dt.floor("h")
    h = x.groupby(SECTION_KEYS).agg(miles=("miles", "sum"), secs=("dt", "sum"), n_trips=("trip_id", "nunique")).reset_index()
    h["length_mi"] = h.section_id.map({s["section_id"]: s["length_mi"] for s in c.sections})
    h = h[(h.miles >= MIN_COVERAGE * h.length_mi) & (h.secs > 0)].copy()
    h["speed_mph"] = (h.miles / (h.secs / 3600)).round(2)
    h["travel_time_min"] = (h.length_mi / h.speed_mph * 60).round(2)
    h["hour_start_local"] = local_iso(h.hour_start_utc)
    h["hour_start_utc"] = h.hour_start_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    h["corridor_id"], h["source"], h["feed_version"] = c.id, "gtfs_realtime_observed", ""
    return h[["corridor_id", "hour_start_utc", "hour_start_local", "route", "direction", "section_id", "speed_mph",
              "travel_time_min", "length_mi", "n_trips", "source", "feed_version"]]


def crossing_time(s: np.ndarray, t: np.ndarray, b: float, after: float = -np.inf):
    """Time the bus first crosses position b (after time `after`), interpolated between two pings."""
    for i in range(len(s) - 1):
        if t[i + 1] <= after or t[i + 1] - t[i] > CROSS_GAP_S:
            continue
        lo, hi = s[i] - b, s[i + 1] - b
        if lo == 0:
            return t[i]
        if lo * hi < 0 or hi == 0:
            return t[i] + (t[i + 1] - t[i]) * (-lo) / (hi - lo)
    return None


def focus_traversals(p: pd.DataFrame, c: PolylineCorridor) -> pd.DataFrame:
    rows = []
    for (vehicle, trip), g in p.groupby(["vehicle_id", "trip_id"], sort=False):
        s, t = g.s.to_numpy(), g.ts.to_numpy(dtype=float)
        if len(s) < 2 or s[-1] == s[0]:
            continue
        up = s[-1] > s[0]
        for f in c.focus:
            enter_at, exit_at = (f["start_mi"], f["end_mi"]) if up else (f["end_mi"], f["start_mi"])
            t0 = crossing_time(s, t, enter_at)
            t1 = crossing_time(s, t, exit_at, after=t0) if t0 is not None else None
            if t1 is None or not 0 < t1 - t0 <= MAX_TRAVERSE_S:
                continue
            mph = f["length_mi"] / ((t1 - t0) / 3600)
            if mph <= MAX_SPEED_MPH:
                rows.append((c.id, f["focus_id"], g.route.iloc[0], c.dir_up if up else c.dir_down, vehicle, trip,
                             t0, round(t1 - t0, 1), round(mph, 2), f["length_mi"]))
    tr = pd.DataFrame(rows, columns=["corridor_id", "focus_id", "route", "direction", "vehicle_id", "trip_id",
                                     "t0", "seconds", "speed_mph", "length_mi"])
    entered = pd.to_datetime(tr.t0, unit="s", utc=True).dt.floor("s")
    tr["entered_local"] = local_iso(entered)
    tr["entered_utc"] = entered.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return tr[["corridor_id", "focus_id", "entered_utc", "entered_local", "route", "direction", "vehicle_id", "trip_id",
               "seconds", "speed_mph", "length_mi"]]


def focus_hourly(tr: pd.DataFrame) -> pd.DataFrame:
    """Summarise traversals by hour. Built from the full monthly traversal file so it is always consistent."""
    t = tr.copy()
    hour = pd.to_datetime(t.entered_utc, utc=True).dt.floor("h")
    t["hour_start_local"] = local_iso(hour)
    t["hour_start_utc"] = hour.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    g = t.groupby(["corridor_id", "focus_id", "hour_start_utc", "hour_start_local", "route", "direction", "length_mi"])
    h = g.seconds.agg(n_trips="size", median_s="median", p20_s=lambda v: v.quantile(0.2), p80_s=lambda v: v.quantile(0.8)).reset_index()
    h["speed_mph_median"] = (h.length_mi / (h.median_s / 3600)).round(2)
    h[["median_s", "p20_s", "p80_s"]] = h[["median_s", "p20_s", "p80_s"]].round(1)
    return h.sort_values(["hour_start_utc", "focus_id", "route", "direction"])


def merge_monthly(df: pd.DataFrame, month_of: pd.Series, out: pathlib.Path, stem: str, keys: list[str]) -> list[pathlib.Path]:
    written = []
    for month, g in df.groupby(month_of):
        target = out / f"{stem}_{month}.csv"
        if target.exists():
            old = pd.read_csv(target, dtype=str, keep_default_na=False)
            g = pd.concat([old, g.astype(str)]).drop_duplicates(keys, keep="last")
        g.sort_values(keys).to_csv(target, index=False)
        written.append(target)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corridor", type=pathlib.Path, required=True)
    ap.add_argument("--raw", type=pathlib.Path, default=pathlib.Path("data/raw"), help="searched recursively")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/corridors"))
    a = ap.parse_args()
    c = PolylineCorridor(a.corridor)
    out = a.out / c.id / "observed"
    out.mkdir(parents=True, exist_ok=True)
    pings = locate(load(a.raw), c)
    if pings.empty:
        raise SystemExit("no pings on this corridor")

    h = hourly_sections(pings, c)
    merge_monthly(h, h.hour_start_local.str[:7], out, f"{c.id}_observed", SECTION_KEYS)

    tr = focus_traversals(pings, c)
    for path in merge_monthly(tr, tr.entered_local.str[:7], out, f"{c.id}_focus_traversals", TRAVERSAL_KEYS):
        full = pd.read_csv(path, dtype={"route": str, "vehicle_id": str})
        focus_hourly(full).to_csv(path.with_name(path.name.replace("_focus_traversals_", "_focus_hourly_")), index=False)
    pd.DataFrame(c.focus).to_csv(a.out / c.id / "focus_sections.csv", index=False)
    print(f"{len(pings):,} pings on {c.id} -> {len(h):,} section-hours, {len(tr):,} focus traversals")
