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

LIVE_DAYS = 28  # the page compares the timetable with the last four weeks of measured hours

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"))
    ap.add_argument("--template", type=pathlib.Path, default=pathlib.Path("site/template.html"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("_site/index.html"))
    ap.add_argument("--fragment", type=pathlib.Path, help="also write the page without the <html> wrapper or download links")
    a = ap.parse_args()

    h = pd.read_parquet(a.data / "hourly")
    local = h.hour_start_utc.dt.tz_convert(TIMEZONE)
    h["month"] = local.dt.strftime("%Y-%m")
    h["hour"] = local.dt.hour
    h["daytype"] = local.dt.weekday.map(lambda d: "weekday" if d < 5 else ("saturday" if d == 5 else "sunday"))
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

    calitp = pd.read_csv(a.data / "reference" / "calitp_speeds_204.csv")
    files = sorted((a.data / "observed").glob("vermont_observed_*.csv"))[-2:]  # enough for the last LIVE_DAYS
    obs = pd.concat([pd.read_csv(f, dtype={"route": str}) for f in files]) if files else pd.DataFrame()
    live = []
    if len(obs):
        obs["t"] = pd.to_datetime(obs.hour_start_utc, utc=True).dt.tz_convert(TIMEZONE)
        obs = obs[obs.t >= obs.t.max() - pd.Timedelta(days=LIVE_DAYS)]
        for r in obs.itertuples():
            wd = r.t.weekday()
            live.append({"date": r.t.strftime("%Y-%m-%d"), "hour": r.t.hour, "route": r.route, "direction": r.direction,
                         "section": r.section_id, "mph": r.speed_mph, "n": r.n_trips,
                         "day": "weekday" if wd < 5 else ("saturday" if wd == 5 else "sunday")})

    payload = {
        "months": months,
        "series": series,
        "sections": [CORRIDOR] + SECTIONS,
        "breakpoints": [n for n, _ in BREAKPOINTS],
        "calitp": [{"section": r.section_id, "direction": r.direction, "period": r.time_period, "start": r.start_hour,
                    "end": r.end_hour, "p20": r.p20_mph, "p50": r.p50_mph, "p80": r.p80_mph}
                   for r in calitp.itertuples()],
        "calitp_retrieved": calitp.retrieved.iloc[0],
        "live": live,
        "meta": {"rows": int(len(h)), "first": local.min().strftime("%Y-%m-%d"), "last": local.max().strftime("%Y-%m-%d"),
                 "feed_versions": int(h.feed_version.nunique())},
    }
    page = a.template.read_text().replace("/*DATA*/null", json.dumps(payload, separators=(",", ":")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.fragment:
        a.fragment.write_text(page)

    # Publish the archive next to the page so every file has a stable URL.
    site_data = a.out.parent / "data"
    shutil.rmtree(site_data, ignore_errors=True)
    shutil.copytree(a.data, site_data, ignore=shutil.ignore_patterns("raw", "mds_telemetry_*", "vehicle_positions_*"))
    shutil.copy(a.data.parent / "datapackage.json", a.out.parent / "datapackage.json")
    files = sorted(f.relative_to(a.out.parent).as_posix() for f in site_data.rglob("*") if f.is_file())
    listing = "".join(f'<li><a href="../{f}">{f}</a></li>' for f in ["datapackage.json"] + files)
    (site_data / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Vermont Av bus speeds: files</title><body style=\"font:15px/1.6 system-ui;max-width:60ch;margin:2rem auto;padding:0 16px\">"
        f'<h1>Archive files</h1><p>Columns are described in datapackage.json. <a href="../">Back to the charts</a></p><ul>{listing}</ul>')
    page = page.replace("<!--DOWNLOADS-->", ' <a href="data/">Download the files</a>.')
    a.out.write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                     '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
                     + page + "\n</body>\n</html>\n")
    print(f"{a.out}: {a.out.stat().st_size / 1e6:.2f} MB, {len(months)} months, {len(series)} series, {len(live)} live rows")
