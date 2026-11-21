#!/usr/bin/env python3
"""Build the self-contained demo page from the archives.

Aggregates the hourly archive to month x hour-of-day profiles (small enough to
embed), adds the observed comparisons, and inlines everything into
site/template.html.

    python pipeline/build_site.py            -> _site/index.html plus _site/data/ (the downloadable archive)
"""
import argparse
import json
import pathlib
import shutil

import pandas as pd

from corridor import BREAKPOINTS, CORRIDOR, SECTIONS, TIMEZONE
from polyline import PolylineCorridor

LIVE_DAYS = 28  # the page compares the timetable with the last four weeks of measured hours


def profile(h: pd.DataFrame) -> dict:
    """Month x hour-of-day speed profiles for one corridor, small enough to embed."""
    local = h.hour_start_utc.dt.tz_convert(TIMEZONE)
    h = h.assign(month=local.dt.strftime("%Y-%m"), hour=local.dt.hour,
                 daytype=local.dt.weekday.map(lambda d: "weekday" if d < 5 else ("saturday" if d == 5 else "sunday")))
    days_per_month = local.dt.date.groupby(h.month).nunique()
    months = [m for m in sorted(h.month.unique()) if days_per_month[m] >= 10]  # drop stub months
    mi = {m: i for i, m in enumerate(months)}
    g = h[h.month.isin(months)].groupby(["route", "direction", "section_id", "daytype", "month", "hour"]).agg(
        tt=("travel_time_min", "mean"), length=("length_mi", "first")).reset_index()
    g["v"] = (g.length / (g.tt / 60) * 100).round().astype(int)  # mph x 100
    series = {}
    for key, grp in g.groupby(["route", "direction", "section_id", "daytype"]):
        arr = [0] * (len(months) * 24)
        for m, hr, v in zip(grp.month, grp.hour, grp.v):
            arr[mi[m] * 24 + hr] = v
        series["|".join(key)] = arr
    return {"months": months, "series": series,
            "meta": {"rows": int(len(h)), "first": local.min().strftime("%Y-%m-%d"), "last": local.max().strftime("%Y-%m-%d"),
                     "feed_versions": int(h.feed_version.nunique())}}


def live_rows(files: list) -> list:
    """Measured section-hours from the last LIVE_DAYS days."""
    files = files[-2:]
    if not files:
        return []
    obs = pd.concat([pd.read_csv(f, dtype={"route": str}) for f in files])
    obs["t"] = pd.to_datetime(obs.hour_start_utc, utc=True).dt.tz_convert(TIMEZONE)
    obs = obs[obs.t >= obs.t.max() - pd.Timedelta(days=LIVE_DAYS)]
    day = lambda wd: "weekday" if wd < 5 else ("saturday" if wd == 5 else "sunday")
    return [{"date": r.t.strftime("%Y-%m-%d"), "hour": r.t.hour, "route": r.route, "direction": r.direction,
             "section": r.section_id, "mph": r.speed_mph, "n": int(r.n_trips), "day": day(r.t.weekday())} for r in obs.itertuples()]


def traffic_rows(files: list) -> list:
    """General-traffic section-hours (TomTom or HERE files) from the last LIVE_DAYS days."""
    files = files[-2:]
    if not files:
        return []
    t = pd.concat([pd.read_csv(f) for f in files]).dropna(subset=["speed_mph"])
    if t.empty:
        return []
    t["t"] = pd.to_datetime(t.hour_start_utc, utc=True).dt.tz_convert(TIMEZONE)
    t = t[t.t >= t.t.max() - pd.Timedelta(days=LIVE_DAYS)]
    day = lambda wd: "weekday" if wd < 5 else ("saturday" if wd == 5 else "sunday")
    return [{"date": r.t.strftime("%Y-%m-%d"), "hour": r.t.hour, "direction": r.direction, "section": r.section_id,
             "mph": round(float(r.speed_mph), 2), "day": day(r.t.weekday())} for r in t.itertuples()]


def incident_rows(files: list) -> list:
    """TomTom incidents seen in the last LIVE_DAYS days: one row per incident, section and direction, with the local
    clock hours it was active by day type (for the hourly chart) and its type, size and largest delay."""
    if not files:
        return []
    t = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in files])
    if t.empty:
        return []
    first = pd.to_datetime(t.first_seen_utc, utc=True).dt.tz_convert(TIMEZONE)
    last = pd.to_datetime(t.last_seen_utc, utc=True).dt.tz_convert(TIMEZONE)
    start = last.max() - pd.Timedelta(days=LIVE_DAYS)
    day = lambda wd: "weekday" if wd < 5 else ("saturday" if wd == 5 else "sunday")
    out = []
    for r, f, l in zip(t.itertuples(), first, last):
        if l < start:
            continue
        hours = {}
        for ts in pd.date_range(max(f, start).floor("h"), l.floor("h"), freq="h"):
            hours.setdefault(day(ts.weekday()), set()).add(ts.hour)
        out.append({"id": r.incident_id[-16:], "sec": r.section_id, "dir": r.direction, "cat": r.category, "mag": int(r.magnitude or 0),
                    "delay": int(r.max_delay_s) if r.max_delay_s else None, "first": f.strftime("%Y-%m-%d"),
                    "last": l.strftime("%Y-%m-%d"), "hours": {k: sorted(v) for k, v in hours.items()}})
    return out


def history_rows(path: pathlib.Path) -> list:
    """Cal-ITP measured segment speeds rolled up to sections, one row per date, period, line, direction, section."""
    if not path.exists():
        return []
    h = pd.read_csv(path, dtype={"route": str}).dropna(subset=["p50_mph"])
    return [{"date": r.analysis_date, "period": r.period, "route": r.route, "direction": r.direction, "section": r.section_id,
             "p50": float(r.p50_mph), "len": float(r.length_mi)} for r in h.itertuples()]


def jpeg_size(path: pathlib.Path):
    """(width, height) of a JPEG from its frame header, without an imaging library."""
    try:
        b = path.read_bytes()
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            marker, seg = b[i + 1], int.from_bytes(b[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2):
                return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
            i += 2 + seg
    except OSError:
        pass
    return None


def with_sizes(project, site_dir: pathlib.Path):
    """Add each map's pixel width and height so the page can reserve its space before the image loads."""
    if not project:
        return project
    for m in project.get("maps", []):
        wh = jpeg_size(site_dir / m["src"])
        if wh:
            m["w"], m["h"] = wh
    return project


def focus_rows(root: pathlib.Path, cid: str) -> list:
    """Per focus segment and direction: bus passes timed so far, median and spread in seconds."""
    files = sorted((root / "observed").glob(f"{cid}_focus_traversals_*.csv"))
    if not files or not (root / "focus_sections.csv").exists():
        return []
    tr = pd.concat([pd.read_csv(f) for f in files])
    names = pd.read_csv(root / "focus_sections.csv").set_index("focus_id")
    out = []
    for (fid, direction), g in tr.groupby(["focus_id", "direction"]):
        out.append({"id": fid, "name": names.loc[fid, "name"], "length_mi": float(names.loc[fid, "length_mi"]), "direction": direction,
                    "n": int(len(g)), "median_s": round(float(g.seconds.median()), 1), "p20_s": round(float(g.seconds.quantile(.2)), 1),
                    "p80_s": round(float(g.seconds.quantile(.8)), 1), "first": g.entered_local.min()[:10], "last": g.entered_local.max()[:10]})
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"))
    ap.add_argument("--template", type=pathlib.Path, default=pathlib.Path("site/template.html"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("_site/index.html"))
    ap.add_argument("--fragment", type=pathlib.Path, help="also write the page without the <html> wrapper or download links")
    a = ap.parse_args()

    calitp = pd.read_csv(a.data / "reference" / "calitp_speeds_204.csv")
    corridors = {"vermont": {
        **profile(pd.read_parquet(a.data / "hourly")),
        "name": "Vermont Av", "street": "Vermont Av", "ends": ["North", "South"],
        "routes": [["204", "204 Local"], ["754", "754 Rapid"]],
        "directions": ["northbound", "southbound"],
        "sections": [CORRIDOR] + SECTIONS,
        "breakpoints": [n for n, _ in BREAKPOINTS],
        "events": [{"date": "2026-10", "short": "BRT construction starts", "label": "Vermont Transit Corridor BRT groundbreaking (Metro)",
                    "status": "under construction; opening targeted 2028, not confirmed"}],
        "calitp": [{"section": r.section_id, "direction": r.direction, "period": r.time_period, "start": r.start_hour,
                    "end": r.end_hour, "p20": r.p20_mph, "p50": r.p50_mph, "p80": r.p80_mph} for r in calitp.itertuples()],
        "live": live_rows(sorted((a.data / "observed").glob("vermont_observed_*.csv"))),
        "traffic": traffic_rows(sorted((a.data / "traffic").glob("vermont_traffic_*.csv"))),
        "here": traffic_rows(sorted((a.data / "traffic").glob("vermont_here_traffic_*.csv"))),
        "history": history_rows(a.data / "calitp" / "vermont_calitp_history.csv"),
        "incidents": incident_rows(sorted((a.data / "incidents").glob("vermont_incidents_*.csv"))),
        "project": {"title": "Vermont Transit Corridor (bus rapid transit)", "url": "https://www.metro.net/projects/vermont-corridor/",
                    "owner": "LA Metro", "maps": [{"src": "maps/vermont-brt-stations.jpg",
                    "caption": "Vermont Transit Corridor bus rapid transit stations and layovers (subject to change)",
                    "credit": "LA Metro, 2025 (map 25-1768)", "source": "https://www.metro.net/projects/vermont-corridor/"}]},
        "focus": [],
    }}
    planned = []
    for path in sorted(pathlib.Path("corridors").glob("*.json")):
        cfg = json.loads(path.read_text())
        root = a.data / "corridors" / cfg["corridor_id"]
        events = [{**e, "short": e.get("short") or e["label"].split(" (")[0][:40]} for e in cfg.get("events", [])]
        traffic = traffic_rows(sorted((root / "traffic").glob(f"{cfg['corridor_id']}_traffic_*.csv")))
        here = traffic_rows(sorted((root / "traffic").glob(f"{cfg['corridor_id']}_here_traffic_*.csv")))
        incidents = incident_rows(sorted((root / "incidents").glob(f"{cfg['corridor_id']}_incidents_*.csv")))
        if not (root / "hourly").exists():
            # No bus data (Fountain Av): offered in the street picker when general-traffic speeds exist.
            if not traffic:
                planned.append({"name": cfg["name"], "events": cfg.get("events", [])})
                continue
            pc = PolylineCorridor(cfg)
            corridors[cfg["corridor_id"]] = {
                "months": [], "series": {}, "meta": {"rows": 0, "first": "", "last": "", "feed_versions": 0},
                "name": cfg["name"].split(",")[0], "street": cfg["name"].split(",")[0], "ends": cfg.get("ends", ["West", "East"]),
                "routes": [], "directions": [cfg["directions"]["increasing"], cfg["directions"]["decreasing"]],
                "sections": [pc.total] + pc.sections, "breakpoints": [b[0] for b in cfg["breakpoints"]],
                "events": events, "calitp": [], "live": [], "traffic": traffic, "here": here, "incidents": incidents, "project": with_sizes(cfg.get("project"), a.template.parent), "history": [], "focus": [],
            }
            continue
        sec = pd.read_csv(root / "sections.csv")
        sections = sec[sec.section_id == "corridor"].to_dict("records") + sec[sec.section_id != "corridor"].to_dict("records")
        names = [b[0] for b in cfg["breakpoints"]]
        corridors[cfg["corridor_id"]] = {
            **profile(pd.read_parquet(root / "hourly")),
            "name": cfg.get("short_name") or cfg["name"].split(",")[0], "street": cfg["name"].split(",")[0], "ends": cfg.get("ends", ["West", "East"]),
            "routes": [[r, f"Line {r}"] for r in cfg["routes"]],
            "directions": [cfg["directions"]["increasing"], cfg["directions"]["decreasing"]],
            "sections": sections, "breakpoints": names,
            "events": events,
            "calitp": [],
            "live": live_rows(sorted((root / "observed").glob(f"{cfg['corridor_id']}_observed_*.csv"))),
            "traffic": traffic,
            "here": here,
            "incidents": incidents,
            "project": with_sizes(cfg.get("project"), a.template.parent),
            "history": history_rows(root / "calitp" / f"{cfg['corridor_id']}_calitp_history.csv"),
            "focus": focus_rows(root, cfg["corridor_id"]),
        }
    order = ["vermont", "hollywood", "sunset", "pico", "olympic", "westwood", "fountain"]  # street picker order
    with_sizes(corridors["vermont"]["project"], a.template.parent)
    corridors = dict(sorted(corridors.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order)))
    deaths = {}
    fat = a.data / "reference" / "fatalities_ccrs.csv"
    if fat.exists():
        f = pd.read_csv(fat)
        deaths["ccrs"] = f.to_dict("records")
    nat = a.data / "reference" / "fatalities_national.csv"
    if nat.exists():
        deaths["national"] = pd.read_csv(nat).to_dict("records")
    payload = {"corridors": corridors, "planned": planned, "deaths": deaths, "calitp_retrieved": calitp.retrieved.iloc[0],
               "rows": sum(c["meta"]["rows"] for c in corridors.values())}
    page = a.template.read_text().replace("/*DATA*/null", json.dumps(payload, separators=(",", ":")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.fragment:
        a.fragment.write_text(page)

    # Publish the archive next to the page so every file has a stable URL.
    site_data = a.out.parent / "data"
    shutil.rmtree(site_data, ignore_errors=True)
    shutil.copytree(a.data, site_data, ignore=shutil.ignore_patterns("raw", "mds_telemetry_*", "vehicle_positions_*"))
    shutil.copy(a.data.parent / "datapackage.json", a.out.parent / "datapackage.json")
    # Project map snapshots shown under the street picker (site/maps/, credited on the page)
    shutil.rmtree(a.out.parent / "maps", ignore_errors=True)
    if (a.template.parent / "maps").exists():
        shutil.copytree(a.template.parent / "maps", a.out.parent / "maps")
    # Street definitions, referenced from datapackage.json as corridors/<id>.json
    shutil.rmtree(a.out.parent / "corridors", ignore_errors=True)
    shutil.copytree(a.data.parent / "corridors", a.out.parent / "corridors")
    files = sorted(f.relative_to(a.out.parent).as_posix() for f in site_data.rglob("*") if f.is_file())
    defs = sorted(f"corridors/{q.name}" for q in (a.out.parent / "corridors").glob("*.json"))
    listing = "".join(f'<li><a href="../{f}">{f}</a></li>' for f in ["datapackage.json"] + defs + files)
    (site_data / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Vermont Av bus speeds: files</title><body style=\"font:15px/1.6 system-ui;max-width:60ch;margin:2rem auto;padding:0 16px\">"
        f'<h1>Archive files</h1><p>Columns are described in datapackage.json. <a href="../">Back to the charts</a></p><ul>{listing}</ul>')
    page = page.replace("<!--DOWNLOADS-->", ' <a href="data/">Download the files</a>.')
    a.out.write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                     '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
                     + page + "\n</body>\n</html>\n")
    print(f"{a.out}: {a.out.stat().st_size / 1e6:.2f} MB, corridors: " + ", ".join(
        f"{k} ({len(c['months'])} months, {len(c['series'])} series, {len(c['live'])} live rows)" for k, c in corridors.items()))
