#!/usr/bin/env python3
"""Traffic deaths by year for the City of Los Angeles and California, from CCRS, plus national context.

CCRS (California Crash Reporting System, CHP) publishes one Crashes table per year on data.ca.gov, updated daily
and including LAPD reports. This sums `NumberKilled` per year for crashes in the City of Los Angeles (all reporting
agencies, so freeway crashes inside the city that CHP handles are included), for LAPD reports only, and for the
whole state, and writes:

    data/reference/fatalities_ccrs.csv      year, area, killed, crashes, through (latest crash date in the table)
    data/reference/fatalities_national.csv  NHTSA national figures (maintained by hand, with sources)

    python pipeline/fetch_fatalities.py

Cautions: the current year is partial and late reports keep arriving for months; LAPD sends far fewer non-injury
crashes to CCRS from 2021 on, so LAPD crash counts fall by about two thirds while deaths do not. Use deaths, not
crash counts, for trends across 2020/2021.
"""
import csv
import datetime as dt
import json
import pathlib
import re
import urllib.parse
import urllib.request

API = "https://data.ca.gov/api/3/action/"
OUT = pathlib.Path("data/reference/fatalities_ccrs.csv")
NATIONAL = pathlib.Path("data/reference/fatalities_national.csv")
AREAS = {
    "los_angeles_city": "\"City Name\" ILIKE 'Los Angeles'",
    "los_angeles_city_lapd": "\"NCIC Code\" = '1942'",
    "california": "TRUE",
}


def call(action: str, **params) -> dict:
    url = API + action + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "aviary/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=180))["result"]


def main() -> None:
    pkg = call("package_show", id="ccrs")
    tables = {int(m.group(1)): r["id"] for r in pkg["resources"] if (m := re.fullmatch(r"Crashes_(\d{4})", r["name"]))}
    rows = []
    for year in sorted(tables):
        rid = tables[year]
        through = call("datastore_search_sql", sql=f'SELECT MAX("Crash Date Time") mx FROM "{rid}"')["records"][0]["mx"]
        for area, where in AREAS.items():
            rec = call("datastore_search_sql", sql=f'SELECT SUM("NumberKilled"::int) k, COUNT(*) n FROM "{rid}" WHERE {where}')["records"][0]
            rows.append({"year": year, "area": area, "killed": int(rec["k"] or 0), "crashes": int(rec["n"]),
                         "through": (through or "")[:10], "retrieved": dt.date.today().isoformat(), "source": "ccrs"})
        print(year, {r["area"]: r["killed"] for r in rows if r["year"] == year}, "through", (through or "")[:10])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{OUT}: {len(rows)} rows")


if __name__ == "__main__":
    main()
