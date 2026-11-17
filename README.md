# Vermont Av bus speeds

Hourly bus speeds on Vermont Avenue in Los Angeles (LA Metro line 204 Local and 754 Rapid),
2016 to today, with an interactive time-series page. Built as a demo for CoMotion LA.

- **Page:** `docs/index.html` is self-contained. Open it in a browser, or serve `docs/` with GitHub Pages.
- **Archive:** `data/`, described by `datapackage.json` (Frictionless Tabular Data Package).

## What is in the archive

| Path | Contents |
|---|---|
| `data/hourly/year=YYYY/vermont_speeds.parquet` | Every hour since 2016-01-31: corridor plus six sections, both lines, both directions. About 2.2M rows. |
| `data/hourly_csv/vermont_corridor_YYYY.csv.gz` | The corridor rows of the same table as CSV. |
| `data/observed/vermont_observed_hourly.csv` | Speeds measured from live bus GPS. Same columns. Grows as the collector runs. |
| `data/observed/mds_telemetry_*.json.gz` | The GPS pings behind the observed speeds, as OMF MDS 2.0 Telemetry objects. |
| `data/raw/*.ndjson.gz` | Sample of the raw GTFS-realtime vehicle positions as received. |
| `data/reference/calitp_speeds_204.csv` | Cal-ITP measured speeds (20th, 50th, 80th percentile by time of day), rolled up to the same sections. |
| `data/sections.csv`, `data/feed_versions.csv` | Section boundaries; which GTFS version covers which dates. |

Columns of the hourly tables: `hour_start_utc`, `hour_start_local`, `route`, `direction`, `section_id`,
`speed_mph`, `travel_time_min`, `length_mi`, `n_trips`, `source`, `feed_version`.

```python
import pandas as pd
h = pd.read_parquet("data/hourly")                      # all years
pm = h[(h.section_id == "corridor") & (h.route == "204")]
```

## Where the numbers come from

**Ten years of hourly data: the published timetable (`source = gtfs_schedule`).**
LA Metro keeps its bus GTFS in a git repository whose history goes back to 2016
([gitlab.com/LACMTA/gtfs_bus](https://gitlab.com/LACMTA/gtfs_bus)). For each date we take the
version in force, find every 204 and 754 trip running that day, and work out when it passes each
cross street. Speed is section length divided by scheduled running time, so stops and signals are
included. Metro resets running times at service changes from measured trips, so the series follows
real conditions, with a lag. When the line is flat for a year, Metro did not re-time the route;
traffic may still have changed.

**Measured speeds (`source = gtfs_realtime_observed`).**
`pipeline/collect_realtime.py` listens to Metro's public vehicle-position feed
(`wss://api.metro.net`, no key needed) and `pipeline/build_observed.py` turns consecutive GPS pings
into hourly section speeds. No public archive of this feed exists, so the measured series starts
when collection starts. The workflow in `.github/workflows/collect.yml` samples 20 minutes of
every hour and commits the result.

**Independent check.** Cal-ITP publishes stop-to-stop speeds measured from archived GPS for one
recent weekday. On the current timetable the two agree closely (midday about 8.7 mph measured,
8.6 mph scheduled).

## Open Mobility Foundation formats

OMF's Mobility Data Specification covers vehicle telemetry, trips and events for shared and
for-hire modes. It has no transit-bus mode and no roadway-speed table. So:

- GPS pings are exported in the MDS 2.0 **Telemetry** shape (`device_id`, `timestamp`, `location.lat/lng/speed`,
  `trip_ids`, `gtfs_stop_id`). The UUIDs are generated deterministically from Metro's vehicle and trip ids;
  LA Metro is not a registered MDS provider, so `provider_id` is a placeholder.
- The hourly speed table is this project's own schema, documented in `datapackage.json`.

## Rebuilding

```bash
pip install -r requirements.txt
git clone --filter=blob:none https://gitlab.com/LACMTA/gtfs_bus.git /tmp/gtfs_bus
python pipeline/backfill_gtfs.py --repo /tmp/gtfs_bus --out data    # about 10 minutes
python pipeline/fetch_calitp.py
python pipeline/collect_realtime.py --minutes 55 --out data/raw     # live pings
python pipeline/build_observed.py
python pipeline/build_site.py                                       # writes docs/index.html
```

The corridor and its sections are defined once, in `pipeline/corridor.py`.

## Known limits

- Bus speeds include boarding time, so they are lower than general traffic speeds on the same street.
- Five of the 130 GTFS commits are unusable (deletions or broken uploads) and are skipped; the neighbouring version fills in. 2019-01-05 has no data.
- Day types on the page are by day of week; holidays are not separated.
- The hourly collection workflow only runs on a schedule once it is on the repository's default branch.

## Other sources worth adding

- **Swiftly** (LA Metro's GTFS-realtime vendor): official feed, and historical speed exports if the key allows.
- **Cal-ITP data warehouse**: archived GTFS-realtime for LA Metro since about 2022, which would give a measured hourly history. Access is by request.
- **LADOT ATSAC** signal-system detectors and **INRIX / RITIS** probe speeds for general traffic rather than buses.
