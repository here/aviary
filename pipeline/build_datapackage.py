#!/usr/bin/env python3
"""Write datapackage.json (Frictionless Data Package) describing every published file.

Built from the files that exist, so new months and new corridors are picked up automatically.
Run it before build_site.py; the hourly workflow does.

    python pipeline/build_datapackage.py
"""
import argparse
import datetime as dt
import json
import pathlib
import re

import pandas as pd

TABULAR = "tabular-data-resource"

# Columns shared by the scheduled and measured hourly tables.
HOURLY_FIELDS = [
    ("hour_start_utc", "datetime", "Start of the hour, UTC (ISO 8601)."),
    ("hour_start_local", "string", "Start of the hour in America/Los_Angeles with UTC offset, e.g. 2024-05-01T17:00:00-0700."),
    ("route", "string", "LA Metro bus line, e.g. 204, 754, 2, 4, 180, 217."),
    ("direction", "string", "northbound / southbound on Vermont Av; eastbound / westbound on the other corridors."),
    ("section_id", "string", "`corridor` for the whole street, or a section id (S1, S2, ...); see that street's sections file."),
    ("speed_mph", "number", "Average speed over the section in miles per hour, stops and signals included."),
    ("travel_time_min", "number", "Average minutes to traverse the section. Corridor rows sum the section averages."),
    ("length_mi", "number", "Section length in miles."),
    ("n_trips", "integer", "Trips contributing in that hour (corridor rows: the fewest on any section)."),
    ("source", "string", "`gtfs_schedule` = derived from the published timetable; `gtfs_realtime_observed` = measured from bus GPS "
                         "(LA Metro's public feed and Swiftly, duplicates removed)."),
    ("feed_version", "string", "Scheduled rows: publication date and commit of the LACMTA/gtfs_bus version used. Empty for measured rows."),
]
CORRIDOR_ID = ("corridor_id", "string", "Street identifier, matching corridors/<corridor_id>.json.")
TRAFFIC_FIELDS = [
    ("corridor_id", "string", "Street identifier (`vermont`, or matching corridors/<corridor_id>.json)."),
    ("hour_start_utc", "datetime", "Start of the hour, UTC (ISO 8601)."),
    ("hour_start_local", "string", "Start of the hour in America/Los_Angeles with UTC offset."),
    ("direction", "string", "Direction of travel along the street."),
    ("section_id", "string", "`corridor` for the whole street, or a section id; see that street's sections file."),
    ("speed_mph", "number", "General-traffic speed: covered length over summed travel time of the matched road pieces, averaged over the hour's snapshots by travel time."),
    ("free_flow_mph", "number", "Same, at free-flow speed (TomTom speed divided by relative speed)."),
    ("travel_time_min", "number", "Minutes to traverse the section at speed_mph."),
    ("length_mi", "number", "Section length in miles."),
    ("coverage", "number", "Share of the section covered by matched road pieces (mean over snapshots)."),
    ("closed_share", "number", "Share of covered length reported closed or at 0 km/h."),
    ("n_snapshots", "integer", "15-minute snapshots in the hour."),
    ("source", "string", "`tomtom_traffic_flow` = TomTom Orbis Traffic API v2 flow tiles."),
]


def fields(spec):
    return [{"name": n, "type": t, "description": d} for n, t, d in spec]


def schema(spec, key=None):
    s = {"fields": fields(spec)}
    if key:
        s["primaryKey"] = key
    return s


def paths(root: pathlib.Path, pattern: str) -> list[str]:
    return sorted(p.as_posix() for p in root.glob(pattern))


def has_rows(path: pathlib.Path) -> bool:
    try:
        return len(pd.read_csv(path)) > 0
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return False


def csv_schema(path: pathlib.Path, descriptions: dict[str, str]) -> dict:
    """Schema for a small CSV, with types read from the file and descriptions from the table above."""
    df = pd.read_csv(path, nrows=200)
    kind = lambda s: "integer" if pd.api.types.is_integer_dtype(s) else "number" if pd.api.types.is_numeric_dtype(s) else "string"
    return {"fields": [{"name": c, "type": kind(df[c]), **({"description": descriptions[c]} if c in descriptions else {})} for c in df.columns]}


SECTION_DESC = {
    "corridor_id": CORRIDOR_ID[2], "section_id": "Section id; `corridor` is the whole street.", "name": "From cross street to cross street.",
    "start_mi": "Distance along the street's path where the section starts, miles.", "end_mi": "Where it ends, miles.",
    "length_mi": "Section length, miles.", "north_lat": "Northern boundary latitude (Vermont Av runs north-south).",
    "south_lat": "Southern boundary latitude.", "focus_id": "Short segment id (F1, F1a, ...), timed bus by bus.",
}
FEED_DESC = {"feed_version": "GTFS version: publication date and git commit.", "first_date": "First service date it covers.",
             "last_date": "Last service date it covers.", "days": "Number of service days."}
TRAVERSAL_DESC = {
    "corridor_id": CORRIDOR_ID[2], "focus_id": SECTION_DESC["focus_id"], "entered_utc": "When the bus entered the segment, UTC.",
    "entered_local": "Same, Los Angeles time with offset.", "route": "LA Metro bus line.", "direction": "Direction of travel.",
    "vehicle_id": "Vehicle number from the GPS feed.", "trip_id": "GTFS trip id.", "seconds": "Seconds to cross the segment.",
    "speed_mph": "Segment length divided by crossing time, mph.", "length_mi": "Segment length, miles.",
}
FOCUS_HOURLY_DESC = {
    **{k: TRAVERSAL_DESC[k] for k in ("corridor_id", "focus_id", "route", "direction", "length_mi")},
    "hour_start_utc": HOURLY_FIELDS[0][2], "hour_start_local": HOURLY_FIELDS[1][2], "n_trips": "Buses timed through the segment that hour.",
    "median_s": "Middle crossing time, seconds.", "p20_s": "20th percentile crossing time, seconds (faster buses).",
    "p80_s": "80th percentile crossing time, seconds (slower buses).", "speed_mph_median": "Segment length over the middle crossing time, mph.",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("datapackage.json"))
    a = ap.parse_args()
    root = pathlib.Path(".")
    resources = []

    def add(name, title, path, fmt, desc=None, sch=None, **extra):
        """One resource per file. Several files (one per year or month) share a `group` named after the dataset."""
        if not path:
            return
        files = [path] if isinstance(path, str) else path
        for f in files:
            part = re.search(r"(\d{4}(?:-\d{2})?)(?=[^/]*$)|year=(\d{4})", f) if len(files) > 1 else None
            label = (part.group(1) or part.group(2)) if part else None
            r = {"name": f"{name}-{label}" if label else name, "title": f"{title} ({label})" if label else title, "path": f, "format": fmt}
            if label:
                r["group"] = name
            if desc:
                r["description"] = desc
            if sch:
                r["profile"], r["schema"] = TABULAR, sch
            r.update(extra)
            resources.append(r)

    # Vermont Av (the original corridor; files predate the corridors/ layout)
    add("vermont-hourly", "Vermont Av: hourly speeds, whole street and six sections, 2016 onward",
        paths(root, "data/hourly/year=*/vermont_speeds.parquet"), "parquet",
        "Scheduled speeds for lines 204 and 754, Sunset Bl to Athens Station. Hive-partitioned by local year.",
        schema(HOURLY_FIELDS, ["hour_start_utc", "route", "direction", "section_id", "source"]), mediatype="application/vnd.apache.parquet")
    add("vermont-hourly-csv", "Vermont Av: hourly speeds, whole-street rows only", paths(root, "data/hourly_csv/vermont_corridor_*.csv.gz"),
        "csv", None, schema(HOURLY_FIELDS), compression="gz", mediatype="text/csv")
    add("vermont-observed", "Vermont Av: measured hourly speeds from bus GPS", paths(root, "data/observed/vermont_observed_*.csv"), "csv",
        "One file per local month. Measured since November 2026.", schema(HOURLY_FIELDS))
    add("vermont-traffic", "Vermont Av: hourly general-traffic speeds (TomTom)", paths(root, "data/traffic/vermont_traffic_*.csv"), "csv",
        "One file per local month. Collected since November 2026.", schema(TRAFFIC_FIELDS))
    if (root / "data/sections.csv").exists():
        add("vermont-sections", "Vermont Av: sections", "data/sections.csv", "csv", None, csv_schema(root / "data/sections.csv", SECTION_DESC))
    if (root / "data/feed_versions.csv").exists():
        add("vermont-feed-versions", "Vermont Av: timetable version in force for each date range", "data/feed_versions.csv", "csv", None,
            csv_schema(root / "data/feed_versions.csv", FEED_DESC))
    if (root / "data/reference/calitp_speeds_204.csv").exists():
        add("vermont-calitp-reference", "Vermont Av: Cal-ITP measured speeds for line 204 (one-day snapshot)",
            "data/reference/calitp_speeds_204.csv", "csv", "20th, 50th and 80th percentile speeds by time of day, rolled up to the sections.",
            csv_schema(root / "data/reference/calitp_speeds_204.csv", {}))

    # Corridors defined by a path (corridors/<id>.json)
    corridor_names = []
    for cfg_path in sorted(root.glob("corridors/*.json")):
        cfg = json.loads(cfg_path.read_text())
        cid, name = cfg["corridor_id"], cfg["name"]
        d = root / "data" / "corridors" / cid
        has_bus = (d / "hourly").exists()
        add(f"{cid}-traffic", f"{name}: hourly general-traffic speeds (TomTom)", paths(root, f"data/corridors/{cid}/traffic/{cid}_traffic_*.csv"),
            "csv", "One file per local month. Collected since November 2026.", schema(TRAFFIC_FIELDS))
        add(f"{cid}-definition", f"{name}: definition", cfg_path.as_posix(), "json",
            "Street path, section boundaries, bus lines and project dates." + ("" if has_bus else " No bus data for this street yet."),
            mediatype="application/json")
        if not has_bus:
            continue
        corridor_names.append(name.split(",")[0])
        lines = ", ".join(cfg["routes"])
        add(f"{cid}-hourly", f"{name}: hourly scheduled speeds", paths(root, f"data/corridors/{cid}/hourly/year=*/{cid}_speeds.parquet"),
            "parquet", f"Scheduled speeds for lines {lines}. Hive-partitioned by local year.",
            schema([CORRIDOR_ID] + HOURLY_FIELDS, ["hour_start_utc", "route", "direction", "section_id", "source"]),
            mediatype="application/vnd.apache.parquet")
        add(f"{cid}-observed", f"{name}: measured hourly speeds from bus GPS", paths(root, f"data/corridors/{cid}/observed/{cid}_observed_*.csv"),
            "csv", "One file per local month. Measured since November 2026.", schema([CORRIDOR_ID] + HOURLY_FIELDS))
        add(f"{cid}-sections", f"{name}: sections", f"data/corridors/{cid}/sections.csv", "csv", None,
            csv_schema(d / "sections.csv", SECTION_DESC))
        add(f"{cid}-feed-versions", f"{name}: timetable version in force for each date range", f"data/corridors/{cid}/feed_versions.csv",
            "csv", None, csv_schema(d / "feed_versions.csv", FEED_DESC))
        focus = d / "focus_sections.csv"
        if has_rows(focus):
            add(f"{cid}-focus-sections", f"{name}: short segments timed bus by bus", focus.as_posix(), "csv", None, csv_schema(focus, SECTION_DESC))
            trav = paths(root, f"data/corridors/{cid}/observed/{cid}_focus_traversals_*.csv")
            hourly = paths(root, f"data/corridors/{cid}/observed/{cid}_focus_hourly_*.csv")
            if trav:
                add(f"{cid}-focus-traversals", f"{name}: every bus timed through the short segments", trav, "csv", "One file per local month.",
                    csv_schema(root / trav[-1], TRAVERSAL_DESC))
            if hourly:
                add(f"{cid}-focus-hourly", f"{name}: short-segment crossing times by hour", hourly, "csv", "One file per local month.",
                    csv_schema(root / hourly[-1], FOCUS_HOURLY_DESC))

    streets = ["Vermont Av"] + corridor_names
    pkg = {
        "name": "aviary-la-street-speeds",
        "title": "Hourly bus speeds on Los Angeles streets being redesigned: " + ", ".join(streets),
        "description": ("Scheduled hourly bus speeds rebuilt from LA Metro's timetable history (Vermont Av since 2016, other streets since 2018), "
                        "and measured speeds from bus GPS since November 2026. Speeds include stops. Each street's definition file lists "
                        "the project dates on it."),
        "profile": "data-package",
        "version": "0.2.0",
        "created": "2026-11-17T00:00:00Z",
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "homepage": "https://aviary.herebox.org",
        "keywords": ["Los Angeles", "bus speeds", "GTFS", "GTFS-realtime", "road diet", "before and after", "LA Metro", "LADOT"],
        "licenses": [{"name": "CC-BY-4.0", "title": "Creative Commons Attribution 4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}],
        "sources": [
            {"title": "LA Metro bus GTFS (git history)", "path": "https://gitlab.com/LACMTA/gtfs_bus"},
            {"title": "LA Metro realtime API (GTFS-realtime vehicle positions)", "path": "https://api.metro.net"},
            {"title": "Swiftly realtime API for LA Metro (GTFS-realtime vehicle positions)", "path": "https://api.goswift.ly"},
            {"title": "Cal-ITP / Caltrans Average Transit Speeds by Stop", "path": "https://data.ca.gov/dataset/average-transit-speeds-by-stop"},
            {"title": "TomTom Orbis Traffic API v2 (traffic flow tiles)", "path": "https://docs.tomtom.com/traffic-api/documentation/tomtom-orbis-maps/v2/product-information/introduction"},
        ],
        "resources": resources,
    }
    a.out.write_text(json.dumps(pkg, indent=2) + "\n")
    print(f"{a.out}: {len(resources)} resources for {', '.join(streets)}")


if __name__ == "__main__":
    main()
