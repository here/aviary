#!/usr/bin/env python3
"""Turn raw vehicle positions into hourly *observed* speeds on Vermont Av.

Reads the NDJSON written by collect_realtime.py and produces

    data/observed/vermont_observed_YYYY-MM.csv   one file per month, same columns as the schedule archive

and optionally (--export DIR), one pair of files per UTC day for cold storage:

    vehicle_positions_YYYY-MM-DD.ndjson.gz       the day's pings, de-duplicated, as received
    mds_telemetry_YYYY-MM-DD.json.gz             the same pings as OMF MDS 2.0 Telemetry objects

Method: consecutive GPS pings of the same vehicle on the same trip give a
distance travelled along the street (change in latitude) and an elapsed time.
Each pair is credited to the section containing its midpoint; the hourly
speed of a section is total distance / total time, so signal and stop dwell
are included, which is what a rider experiences.
"""
import argparse
import glob
import gzip
import json
import pathlib
import uuid

import pandas as pd

from corridor import CORRIDOR, LON_TOLERANCE, MILES_PER_DEG_LAT, SECTIONS, TIMEZONE, VERMONT_LON

MAX_GAP_S = 300        # ignore pairs of pings further apart than this
MAX_SPEED_MPH = 55     # discard GPS jumps
MIN_COVERAGE = 0.5     # a section needs pings covering at least half its length in the hour
MDS_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "api.metro.net")  # stable demo UUIDs; not an OMF-registered provider


def load(raw_dir: pathlib.Path) -> pd.DataFrame:
    rows = []
    for path in sorted(glob.glob(str(raw_dir / "**" / "vehicle_positions_*.ndjson*"), recursive=True)):
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    v, trip, pos = r["vehicle"], r["vehicle"].get("trip", {}), r["vehicle"]["position"]
                    rows.append((v["vehicle"]["id"], trip.get("tripId"), trip.get("startDate"), r.get("route_code"),
                                 int(v["timestamp"]), pos["latitude"], pos["longitude"], pos.get("speed"),
                                 pos.get("bearing"), v.get("stopId"), v.get("currentStatus"), line.strip()))
                except (KeyError, ValueError, TypeError):
                    continue
    df = pd.DataFrame(rows, columns=["vehicle_id", "trip_id", "start_date", "route", "ts", "lat", "lon",
                                     "gps_speed_mps", "bearing", "stop_id", "status", "raw"])
    return df.dropna(subset=["trip_id"]).drop_duplicates(["vehicle_id", "ts"]).sort_values(["vehicle_id", "trip_id", "ts"])


def hourly(df: pd.DataFrame) -> pd.DataFrame:
    df = df[(df.lon - VERMONT_LON).abs() < LON_TOLERANCE]
    g = df.groupby(["vehicle_id", "trip_id"], sort=False)
    p = df.assign(dt=g.ts.diff(), dlat=g.lat.diff(), mid_lat=(df.lat + g.lat.shift()) / 2, mid_ts=(df.ts + g.ts.shift()) / 2)
    p = p[(p.dt > 0) & (p.dt <= MAX_GAP_S)].copy()
    # direction of the whole trip, from its first and last ping
    net = g.lat.agg(lambda s: s.iloc[-1] - s.iloc[0]).rename("net").reset_index()
    p = p.merge(net, on=["vehicle_id", "trip_id"])
    p = p[p.net != 0]
    p["direction"] = p.net.gt(0).map({True: "northbound", False: "southbound"})
    p["miles"] = p.dlat * MILES_PER_DEG_LAT * p.net.gt(0).map({True: 1, False: -1})  # progress, backwards jitter cancels
    p = p[(p.miles / (p.dt / 3600)).abs() <= MAX_SPEED_MPH]
    p["section_id"] = None
    for s in SECTIONS:
        p.loc[(p.mid_lat <= s["north_lat"]) & (p.mid_lat > s["south_lat"]), "section_id"] = s["section_id"]
    p = p.dropna(subset=["section_id"])
    p["hour_start_utc"] = pd.to_datetime(p.mid_ts, unit="s", utc=True).dt.floor("h")

    keys = ["hour_start_utc", "route", "direction", "section_id"]
    h = p.groupby(keys).agg(miles=("miles", "sum"), secs=("dt", "sum"), n_trips=("trip_id", "nunique")).reset_index()
    length = {s["section_id"]: s["length_mi"] for s in SECTIONS}
    h["length_mi"] = h.section_id.map(length)
    h = h[(h.miles >= MIN_COVERAGE * h.length_mi) & (h.secs > 0)].copy()
    h["speed_mph"] = h.miles / (h.secs / 3600)
    h["travel_time_min"] = h.length_mi / h.speed_mph * 60

    c = h.groupby(keys[:3]).agg(travel_time_min=("travel_time_min", "sum"), n_sections=("section_id", "size"),
                                n_trips=("n_trips", "min")).reset_index()
    c = c[c.n_sections == len(SECTIONS)].drop(columns="n_sections")
    c["section_id"], c["length_mi"] = "corridor", CORRIDOR["length_mi"]
    c["speed_mph"] = c.length_mi / (c.travel_time_min / 60)
    h = pd.concat([h.drop(columns=["miles", "secs"]), c], ignore_index=True)

    h["hour_start_local"] = h.hour_start_utc.dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    h["hour_start_utc"] = h.hour_start_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    h["source"], h["feed_version"] = "gtfs_realtime_observed", ""
    h[["speed_mph", "travel_time_min"]] = h[["speed_mph", "travel_time_min"]].round(2)
    return h[["hour_start_utc", "hour_start_local", "route", "direction", "section_id", "speed_mph",
              "travel_time_min", "length_mi", "n_trips", "source", "feed_version"]].sort_values(keys)


def export_daily(df: pd.DataFrame, out_dir: pathlib.Path) -> None:
    """Write de-duplicated raw pings and MDS 2.0 Telemetry, one file per UTC day.

    MDS: https://github.com/openmobilityfoundation/mobility-data-specification
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    uid = lambda *parts: str(uuid.uuid5(MDS_NAMESPACE, "/".join(map(str, parts))))
    provider = uid("LACMTA")
    df = df.assign(day=pd.to_datetime(df.ts, unit="s", utc=True).dt.strftime("%Y-%m-%d"))
    for day, g in df.groupby("day"):
        items = []
        for r in g.itertuples():
            loc = {"lat": r.lat, "lng": r.lon}
            if pd.notna(r.gps_speed_mps):
                loc["speed"] = r.gps_speed_mps
            if pd.notna(r.bearing):
                loc["heading"] = r.bearing
            item = {"device_id": uid("vehicle", r.vehicle_id), "provider_id": provider,
                    "telemetry_id": uid("telemetry", r.vehicle_id, r.ts), "timestamp": r.ts * 1000,
                    "trip_ids": [uid("trip", r.start_date, r.trip_id)], "journey_id": None,
                    "location": loc, "location_type": "street"}
            if r.status == "STOPPED_AT" and r.stop_id:
                item["gtfs_stop_id"] = r.stop_id
            items.append(item)
        with gzip.open(out_dir / f"vehicle_positions_{day}.ndjson.gz", "wt") as fh:
            fh.write("\n".join(g.sort_values("ts").raw) + "\n")
        with gzip.open(out_dir / f"mds_telemetry_{day}.json.gz", "wt") as fh:
            json.dump({"version": "2.0.0", "telemetry": items}, fh, separators=(",", ":"))


KEYS = ["hour_start_utc", "route", "direction", "section_id"]


def write_monthly(h: pd.DataFrame, out_dir: pathlib.Path) -> None:
    """Merge into the per-month files; a re-measured hour replaces the earlier row."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for month, g in h.groupby(h.hour_start_local.str[:7]):
        target = out_dir / f"vermont_observed_{month}.csv"
        if target.exists():
            old = pd.read_csv(target, dtype={"route": str, "feed_version": str}, keep_default_na=False)
            g = pd.concat([old, g.astype({"route": str})]).drop_duplicates(KEYS, keep="last")
        g.sort_values(KEYS).to_csv(target, index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", type=pathlib.Path, default=pathlib.Path("data/raw"), help="searched recursively")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/observed"))
    ap.add_argument("--export", type=pathlib.Path, help="also write daily raw + MDS telemetry files here")
    a = ap.parse_args()
    pings = load(a.raw)
    if pings.empty:
        raise SystemExit("no pings found")
    h = hourly(pings)
    write_monthly(h, a.out)
    if a.export:
        export_daily(pings, a.export)
    print(f"{len(pings):,} pings -> {len(h):,} hourly rows")
