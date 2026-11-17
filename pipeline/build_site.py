#!/usr/bin/env python3
"""Build the self-contained demo page from the archives.

Aggregates the hourly archive to month x hour-of-day profiles (small enough to
embed), adds the observed comparisons, and inlines everything into
site/template.html.

    python pipeline/build_site.py            -> docs/index.html (open it directly, or serve with GitHub Pages)
"""
import argparse
import json
import pathlib

import pandas as pd

from corridor import BREAKPOINTS, CORRIDOR, SECTIONS, TIMEZONE

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"))
    ap.add_argument("--template", type=pathlib.Path, default=pathlib.Path("site/template.html"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("docs/index.html"))
    ap.add_argument("--fragment", type=pathlib.Path, help="also write the page without the <html> wrapper")
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
    obs_path = a.data / "observed" / "vermont_observed_hourly.csv"
    obs = pd.read_csv(obs_path, dtype={"route": str}) if obs_path.exists() else pd.DataFrame()
    live = []
    for r in obs.itertuples():
        t = pd.Timestamp(r.hour_start_utc).tz_convert(TIMEZONE)
        live.append({"date": t.strftime("%Y-%m-%d"), "hour": t.hour, "route": r.route, "direction": r.direction,
                     "section": r.section_id, "mph": r.speed_mph, "n": r.n_trips})

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
    a.out.write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                     '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
                     + page + "\n</body>\n</html>\n")
    if a.fragment:
        a.fragment.write_text(page)
    print(f"{a.out}: {a.out.stat().st_size / 1e6:.2f} MB, {len(months)} months, {len(series)} series, {len(live)} live rows")
