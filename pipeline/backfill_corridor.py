#!/usr/bin/env python3
"""Backfill hourly scheduled bus speeds for a corridor defined by a path (corridors/<id>.json).

Same method and output columns as backfill_gtfs.py (which handles Vermont Av), plus a
`corridor_id` column, for streets that are not straight north-south.

    python pipeline/backfill_corridor.py --corridor corridors/sunset.json --repo /path/to/gtfs_bus --start 2018-01-01

Writes data/corridors/<id>/hourly/year=YYYY/<id>_speeds.parquet, sections.csv and feed_versions.csv.
"""
import argparse
import datetime as dt
import pathlib

import numpy as np
import pandas as pd

from backfill_gtfs import active_services, list_versions, read_zip, to_seconds
from corridor import TIMEZONE
from polyline import ON_LINE_MI, SNAP_MI, PolylineCorridor


def feed_profile(z, c: PolylineCorridor):
    rd = lambda name, **k: pd.read_csv(z.open(name), dtype=str, encoding="utf-8-sig", **k)
    routes = rd("routes.txt")
    routes["route"] = routes.route_id.str.split("-").str[0]  # "2-13108" -> "2"; short names vary over the years
    routes = routes[routes.route.isin(c.routes)][["route_id", "route"]]
    trips = rd("trips.txt").merge(routes)[["trip_id", "service_id", "route"]]
    st = rd("stop_times.txt", usecols=["trip_id", "arrival_time", "stop_id", "stop_sequence"])
    st = st[st.trip_id.isin(trips.trip_id)]
    stops = rd("stops.txt", usecols=["stop_id", "stop_lat", "stop_lon"]).astype({"stop_lat": float, "stop_lon": float})
    stops = stops[stops.stop_id.isin(st.stop_id.unique())].copy()
    stops["s"], stops["off"] = c.locate(stops.stop_lat.to_numpy(), stops.stop_lon.to_numpy())
    st = st.merge(stops[stops.off < ON_LINE_MI][["stop_id", "s"]], on="stop_id")
    st["t"] = to_seconds(st.arrival_time)
    st["seq"] = st.stop_sequence.astype(int)
    st = st.sort_values(["trip_id", "seq"])

    rows = []
    for trip_id, g in st.groupby("trip_id", sort=False):
        s, t = g.s.to_numpy(), g.t.to_numpy()
        if len(s) < 2 or s[0] == s[-1]:
            continue
        direction = c.dir_up if s[-1] > s[0] else c.dir_down
        if direction == c.dir_down:
            s, t = s[::-1], t[::-1]
        if np.any(np.diff(s) <= 0):
            keep = np.concatenate([[True], np.diff(np.maximum.accumulate(s)) > 0])
            s, t = s[keep], t[keep]
        covered = (c.breaks >= s[0] - SNAP_MI) & (c.breaks <= s[-1] + SNAP_MI)
        cross = np.interp(c.breaks, s, t)
        for i, sec in enumerate(c.sections):
            if covered[i] and covered[i + 1]:
                secs = abs(cross[i + 1] - cross[i])
                if secs > 0:
                    rows.append((trip_id, direction, sec["section_id"], int((cross[i] + cross[i + 1]) / 2 // 3600), secs))
    trav = pd.DataFrame(rows, columns=["trip_id", "direction", "section_id", "svc_hour", "secs"]).merge(trips)
    prof = trav.groupby(["service_id", "route", "direction", "section_id", "svc_hour"]).agg(
        secs_sum=("secs", "sum"), n_trips=("secs", "size")).reset_index()
    cal = rd("calendar.txt")
    try:
        cald = rd("calendar_dates.txt")
    except KeyError:
        cald = pd.DataFrame(columns=["service_id", "date", "exception_type"])
    used = set(prof.service_id)
    return prof, cal[cal.service_id.isin(used)], cald[cald.service_id.isin(used)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corridor", type=pathlib.Path, required=True)
    ap.add_argument("--repo", type=pathlib.Path, required=True, help="clone of gitlab.com/LACMTA/gtfs_bus")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/corridors"))
    ap.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2018, 1, 1))
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today() - dt.timedelta(days=1))
    a = ap.parse_args()
    c = PolylineCorridor(a.corridor)

    versions = list_versions(a.repo)
    before = [v for v in versions if v[1] < a.start]
    versions = before[-3:] + [v for v in versions if v[1] >= a.start]  # keep a few earlier ones to cover the first dates
    feeds = []
    for n, (commit, cdate) in enumerate(versions, 1):
        try:
            prof, cal, cald = feed_profile(read_zip(a.repo, commit), c)
        except Exception as exc:
            print(f"[{n}/{len(versions)}] {cdate} {commit[:8]} SKIPPED: {exc!r}", flush=True)
            continue
        days = active_services(cal, cald)
        feeds.append((commit[:8], cdate, prof, days))
        print(f"[{n}/{len(versions)}] {cdate} {commit[:8]} services={prof.service_id.nunique()} days={len(days)}", flush=True)

    chosen, d = {}, a.start
    while d <= a.end:
        pick = next((i for i in range(len(feeds) - 1, -1, -1) if feeds[i][1] <= d and d in feeds[i][3]), None)
        if pick is None:
            pick = next((i for i in range(len(feeds)) if d in feeds[i][3]), None)
        if pick is not None:
            chosen[d] = pick
        d += dt.timedelta(days=1)

    frames = []
    for i, (commit, cdate, prof, days) in enumerate(feeds):
        dates = [d for d, p in chosen.items() if p == i]
        if dates:
            ds = pd.DataFrame([(d, s) for d in dates for s in days[d]], columns=["service_date", "service_id"])
            f = ds.merge(prof, on="service_id")
            f["feed_version"] = f"{cdate.isoformat()}_{commit}"
            frames.append(f)
    x = pd.concat(frames, ignore_index=True)
    naive = pd.to_datetime(x.service_date) + pd.to_timedelta(x.svc_hour, unit="h")
    x["hour_start_utc"] = naive.dt.tz_localize(TIMEZONE, ambiguous=True, nonexistent="shift_forward").dt.tz_convert("UTC")
    keys = ["hour_start_utc", "route", "direction", "section_id"]
    h = x.groupby(keys).agg(secs_sum=("secs_sum", "sum"), n_trips=("n_trips", "sum"),
                            feed_version=("feed_version", "max")).reset_index()
    h["length_mi"] = h.section_id.map({s["section_id"]: s["length_mi"] for s in c.sections})
    h["travel_time_min"] = h.secs_sum / h.n_trips / 60

    # corridor row only where one route covers every section in that hour
    t = h.groupby(keys[:3]).agg(travel_time_min=("travel_time_min", "sum"), n_sections=("section_id", "size"),
                                n_trips=("n_trips", "min"), feed_version=("feed_version", "max")).reset_index()
    t = t[t.n_sections == len(c.sections)].drop(columns="n_sections")
    t["section_id"], t["length_mi"] = "corridor", c.total["length_mi"]
    h = pd.concat([h.drop(columns="secs_sum"), t], ignore_index=True)

    h["speed_mph"] = (h.length_mi / (h.travel_time_min / 60)).round(2)
    h["travel_time_min"] = h.travel_time_min.round(2)
    h["hour_start_local"] = h.hour_start_utc.dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    h["source"], h["corridor_id"] = "gtfs_schedule", c.id
    h = h[["corridor_id", "hour_start_utc", "hour_start_local", "route", "direction", "section_id", "speed_mph",
           "travel_time_min", "length_mi", "n_trips", "source", "feed_version"]].sort_values(keys)

    root = a.out / c.id
    for y, g in h.groupby(h.hour_start_utc.dt.tz_convert(TIMEZONE).dt.year):
        p = root / "hourly" / f"year={y}"
        p.mkdir(parents=True, exist_ok=True)
        g.to_parquet(p / f"{c.id}_speeds.parquet", index=False, compression="zstd")
        print(f"{y}: {len(g):,} rows")
    pd.DataFrame(c.sections + [c.total]).to_csv(root / "sections.csv", index=False)
    fv = pd.DataFrame([(d, f"{feeds[i][1].isoformat()}_{feeds[i][0]}") for d, i in sorted(chosen.items())],
                      columns=["date", "feed_version"])
    fv.groupby("feed_version").agg(first_date=("date", "min"), last_date=("date", "max"), days=("date", "size")) \
        .reset_index().sort_values("first_date").to_csv(root / "feed_versions.csv", index=False)
    print(f"total {len(h):,} rows, {h.hour_start_utc.min()} .. {h.hour_start_utc.max()}")


if __name__ == "__main__":
    main()
