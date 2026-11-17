#!/usr/bin/env python3
"""Backfill hourly *scheduled* bus speeds on Vermont Av from GTFS history.

LA Metro publishes its bus GTFS in a git repository whose history reaches back
to 2016 (https://gitlab.com/LACMTA/gtfs_bus). Every version carries the
timetable Metro ran in that period, and Metro re-times the timetable at each
service change from observed running times. This script walks every version
and reconstructs, for each hour of each day, how fast the timetable has buses
moving along Vermont Av.

    python pipeline/backfill_gtfs.py --repo /path/to/gtfs_bus --out data

Outputs
    data/hourly/year=YYYY/vermont_speeds.parquet   all sections, hourly
    data/hourly_csv/vermont_corridor_YYYY.csv.gz    corridor rows only
    data/feed_versions.csv                          which GTFS version covers which dates
"""
import argparse
import datetime as dt
import io
import pathlib
import subprocess
import zipfile

import numpy as np
import pandas as pd

from corridor import (
    BREAKPOINTS,
    CORRIDOR,
    LON_TOLERANCE,
    ROUTES,
    SECTIONS,
    SNAP_TOLERANCE,
    TIMEZONE,
    VERMONT_LON,
)

BP_LATS = np.array([lat for _, lat in BREAKPOINTS])  # north -> south
DOW = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def list_versions(repo: pathlib.Path) -> list[tuple[str, dt.date]]:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "--reverse", "--format=%H %ad", "--date=short", "--", "gtfs_bus.zip"],
        check=True, capture_output=True, text=True,
    ).stdout.split("\n")
    return [(l.split()[0], dt.date.fromisoformat(l.split()[1])) for l in out if l.strip()]


def read_zip(repo: pathlib.Path, commit: str) -> zipfile.ZipFile:
    blob = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:gtfs_bus.zip"], check=True, capture_output=True
    ).stdout
    return zipfile.ZipFile(io.BytesIO(blob))


def to_seconds(col: pd.Series) -> pd.Series:
    parts = col.str.strip().str.split(":", expand=True).astype(float)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def feed_profile(z: zipfile.ZipFile):
    """Return (traversals per service_id/hour, calendar, calendar_dates)."""
    rd = lambda name, **k: pd.read_csv(z.open(name), dtype=str, encoding="utf-8-sig", **k)
    routes = rd("routes.txt")
    routes = routes[routes.route_short_name.isin(ROUTES)][["route_id", "route_short_name"]]
    trips = rd("trips.txt").merge(routes)[["trip_id", "service_id", "route_short_name"]]
    st = rd("stop_times.txt", usecols=["trip_id", "arrival_time", "stop_id", "stop_sequence"])
    st = st[st.trip_id.isin(trips.trip_id)]
    stops = rd("stops.txt", usecols=["stop_id", "stop_lat", "stop_lon"]).astype({"stop_lat": float, "stop_lon": float})
    st = st.merge(stops, on="stop_id")
    st = st[(st.stop_lon - VERMONT_LON).abs() < LON_TOLERANCE].copy()
    st["t"] = to_seconds(st.arrival_time)
    st["seq"] = st.stop_sequence.astype(int)
    st = st.sort_values(["trip_id", "seq"])

    rows = []
    for trip_id, g in st.groupby("trip_id", sort=False):
        lat, t = g.stop_lat.to_numpy(), g.t.to_numpy()
        if len(lat) < 2 or lat[0] == lat[-1]:
            continue
        direction = "northbound" if lat[-1] > lat[0] else "southbound"
        if direction == "southbound":
            lat, t = lat[::-1], t[::-1]  # np.interp wants increasing x
        if np.any(np.diff(lat) <= 0):
            keep = np.concatenate([[True], np.diff(np.maximum.accumulate(lat)) > 0])
            lat, t = lat[keep], t[keep]
        covered = (BP_LATS >= lat[0] - SNAP_TOLERANCE) & (BP_LATS <= lat[-1] + SNAP_TOLERANCE)
        cross = np.interp(BP_LATS, lat, t)  # clamps to end stops within tolerance
        for i, sec in enumerate(SECTIONS):
            if covered[i] and covered[i + 1]:
                secs = abs(cross[i + 1] - cross[i])
                if secs <= 0:
                    continue
                mid = (cross[i] + cross[i + 1]) / 2
                rows.append((trip_id, direction, sec["section_id"], int(mid // 3600), secs))
    trav = pd.DataFrame(rows, columns=["trip_id", "direction", "section_id", "svc_hour", "secs"]).merge(trips)
    prof = (
        trav.groupby(["service_id", "route_short_name", "direction", "section_id", "svc_hour"])
        .agg(secs_sum=("secs", "sum"), n_trips=("secs", "size"))
        .reset_index()
        .rename(columns={"route_short_name": "route"})
    )
    cal = rd("calendar.txt")
    try:
        cald = rd("calendar_dates.txt")
    except KeyError:
        cald = pd.DataFrame(columns=["service_id", "date", "exception_type"])
    used = set(prof.service_id)
    return prof, cal[cal.service_id.isin(used)], cald[cald.service_id.isin(used)]


def active_services(cal: pd.DataFrame, cald: pd.DataFrame) -> dict[dt.date, set[str]]:
    days: dict[dt.date, set[str]] = {}
    for r in cal.itertuples():
        d, end = dt.datetime.strptime(r.start_date, "%Y%m%d").date(), dt.datetime.strptime(r.end_date, "%Y%m%d").date()
        while d <= end:
            if getattr(r, DOW[d.weekday()]) == "1":
                days.setdefault(d, set()).add(r.service_id)
            d += dt.timedelta(days=1)
    for r in cald.itertuples():
        d = dt.datetime.strptime(r.date, "%Y%m%d").date()
        if r.exception_type == "1":
            days.setdefault(d, set()).add(r.service_id)
        elif d in days:
            days[d].discard(r.service_id)
    return {d: s for d, s in days.items() if s}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", type=pathlib.Path, required=True, help="clone of gitlab.com/LACMTA/gtfs_bus")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data"))
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today() - dt.timedelta(days=1))
    a = ap.parse_args()

    versions = list_versions(a.repo)
    feeds = []  # (commit, commit_date, profile, {date: services})
    for n, (commit, cdate) in enumerate(versions, 1):
        try:
            prof, cal, cald = feed_profile(read_zip(a.repo, commit))
        except Exception as exc:  # a malformed historic upload should not stop the run
            print(f"[{n}/{len(versions)}] {cdate} {commit[:8]} SKIPPED: {exc!r}", flush=True)
            continue
        days = active_services(cal, cald)
        feeds.append((commit[:8], cdate, prof, days))
        print(f"[{n}/{len(versions)}] {cdate} {commit[:8]} services={prof.service_id.nunique()} days={len(days)}", flush=True)

    # For each date use the newest version published on or before it that has
    # service that day; before the first publication fall back to any version.
    start = min(min(d) for _, _, _, d in feeds if d)
    chosen: dict[dt.date, int] = {}
    d = start
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
        if not dates:
            continue
        ds = pd.DataFrame([(d, s) for d in dates for s in days[d]], columns=["service_date", "service_id"])
        f = ds.merge(prof, on="service_id")
        f["feed_version"] = f"{cdate.isoformat()}_{commit}"
        frames.append(f)
    x = pd.concat(frames, ignore_index=True)

    # GTFS times count from "noon minus 12h" of the service day and can pass 24:00.
    naive = pd.to_datetime(x.service_date) + pd.to_timedelta(x.svc_hour, unit="h")
    local = naive.dt.tz_localize(TIMEZONE, ambiguous=True, nonexistent="shift_forward")
    x["hour_start_utc"] = local.dt.tz_convert("UTC")
    keys = ["hour_start_utc", "route", "direction", "section_id"]
    h = x.groupby(keys).agg(secs_sum=("secs_sum", "sum"), n_trips=("n_trips", "sum"),
                            feed_version=("feed_version", "max")).reset_index()
    length = {s["section_id"]: s["length_mi"] for s in SECTIONS}
    h["length_mi"] = h.section_id.map(length)
    h["travel_time_min"] = h.secs_sum / h.n_trips / 60

    # Corridor row = end-to-end run: sum of mean section times, only when every section has service.
    c = h.groupby(["hour_start_utc", "route", "direction"]).agg(
        travel_time_min=("travel_time_min", "sum"), n_sections=("section_id", "size"),
        n_trips=("n_trips", "min"), feed_version=("feed_version", "max")).reset_index()
    c = c[c.n_sections == len(SECTIONS)].drop(columns="n_sections")
    c["section_id"], c["length_mi"] = "corridor", CORRIDOR["length_mi"]
    h = pd.concat([h.drop(columns="secs_sum"), c], ignore_index=True)

    h["speed_mph"] = (h.length_mi / (h.travel_time_min / 60)).round(2)
    h["travel_time_min"] = h.travel_time_min.round(2)
    h["hour_start_local"] = h.hour_start_utc.dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    h["source"] = "gtfs_schedule"
    h = h[["hour_start_utc", "hour_start_local", "route", "direction", "section_id", "speed_mph",
           "travel_time_min", "length_mi", "n_trips", "source", "feed_version"]].sort_values(
        ["hour_start_utc", "route", "direction", "section_id"])
    year = h.hour_start_utc.dt.tz_convert(TIMEZONE).dt.year

    (a.out / "hourly_csv").mkdir(parents=True, exist_ok=True)
    for y, g in h.groupby(year):
        p = a.out / "hourly" / f"year={y}"
        p.mkdir(parents=True, exist_ok=True)
        g.to_parquet(p / "vermont_speeds.parquet", index=False, compression="zstd")
        gc = g[g.section_id == "corridor"].copy()
        gc["hour_start_utc"] = gc.hour_start_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        gc.to_csv(a.out / "hourly_csv" / f"vermont_corridor_{y}.csv.gz", index=False)
        print(f"{y}: {len(g):,} rows ({len(gc):,} corridor)")

    fv = pd.DataFrame([(d, f"{feeds[i][1].isoformat()}_{feeds[i][0]}") for d, i in sorted(chosen.items())],
                      columns=["date", "feed_version"])
    fv = fv.groupby("feed_version").agg(first_date=("date", "min"), last_date=("date", "max"),
                                        days=("date", "size")).reset_index().sort_values("first_date")
    fv.to_csv(a.out / "feed_versions.csv", index=False)
    print(f"total {len(h):,} rows, {h.hour_start_utc.min()} .. {h.hour_start_utc.max()}")


if __name__ == "__main__":
    main()
