# Aviary: LA street speeds, before and after

Hourly bus speeds on Los Angeles streets being redesigned, starting with Vermont Avenue (LA Metro lines 204 and 754,
2016 to today), with live GPS collection so each project has a measured "before". Built as a demo for CoMotion LA.

**Outputs:** [aviary.herebox.org](https://aviary.herebox.org) (live charts) · [here.github.io/aviary](https://here.github.io/aviary/) (GitHub Pages mirror with data downloads; not live until Pages and Actions are enabled)

**LADOT and Metro projects:** [Hollywood Blvd Safety and Mobility](https://ladotlivablestreets.org/projects/hollywood-blvd) · [Sunset Blvd / Cesar Chavez (Sunset East)](https://ladotlivablestreets.org/projects/sunset) · [Fountain Av](docs/projects/fountain-av.md) · [Vermont Transit Corridor BRT](https://boardagendas.metro.net/board-report/2026-0025/) · [LADOT Livable Streets](https://ladotlivablestreets.org) · [LADOT news](https://ladot.lacity.gov/dotnews)

## Data sources

| Source | Used for | Access |
|---|---|---|
| [LA Metro bus GTFS history](https://gitlab.com/LACMTA/gtfs_bus) | Scheduled hourly speeds since 2016 | Open |
| [LA Metro realtime API](https://api.metro.net) (`wss://api.metro.net`) | Live bus GPS, collected every minute | Open, no key |
| [Cal-ITP Average Transit Speeds by Stop](https://data.ca.gov/dataset/average-transit-speeds-by-stop) | Independent measured-speed check | Open |
| [GBFS feeds](https://github.com/MobilityData/gbfs/blob/master/systems.csv) (Bird, Metro Bike Share) | Shared bike and scooter availability | Open |
| Cal-ITP GTFS-realtime archive | Measured bus history back to about 2022 | By request |
| LADOT MDS trip data | Bike and scooter trips before and after | By request |
| Swiftly API | Official Metro realtime feed and possible history | Key requested |

Formats: Parquet and CSV described by a Frictionless `datapackage.json`; GPS pings also as Open Mobility Foundation MDS 2.0 Telemetry.

## Live endpoints

| Output | Link | State |
|---|---|---|
| Charts page | https://aviary.herebox.org | Live |
| Bus collector status | https://aviary.herebox.org/api/status | Live, every minute (lines 204, 754, 2, 4) |
| Archived bus pings | https://aviary.herebox.org/api/files?prefix=raw/ | Live |
| Bike and scooter collector status | https://aviary.herebox.org/gbfs/status | Live, every 10 minutes |
| GitHub Pages mirror | https://here.github.io/aviary/ | Not live until Pages and Actions are enabled |

## Project notes

Sourced status notes: [Hollywood Blvd](docs/projects/hollywood-blvd.md), [Fountain Av](docs/projects/fountain-av.md), and
[the expansion plan](docs/EXPANSION_PLAN.md) for Sunset East and Vermont BRT. Dates and figures there come from web search
summaries and need re-checking before publication.

## Build it yourself

- **Page:** `python pipeline/build_site.py` writes a self-contained `_site/index.html` plus the downloadable archive. The workflow publishes it to GitHub Pages and Cloudflare.
- **Archive:** `data/`, described by `datapackage.json`.
- **Handoff notes for agents:** `AGENTS.md`.

## What is in the archive

| Path | Contents |
|---|---|
| `data/hourly/year=YYYY/vermont_speeds.parquet` | Every hour since 2016-01-31: corridor plus six sections, both lines, both directions. About 2.2M rows. |
| `data/hourly_csv/vermont_corridor_YYYY.csv.gz` | The corridor rows of the same table as CSV. |
| `data/observed/vermont_observed_YYYY-MM.csv` | Speeds measured from live bus GPS, one file per month. Same columns. Grows as the collector runs. |
| `data/observed/sample/mds_telemetry_*.json.gz` | Sample of the GPS pings as OMF MDS 2.0 Telemetry objects. Daily files go to R2 (`mds/`), not git. |
| `data/raw/*.ndjson.gz` | Sample of the raw GTFS-realtime vehicle positions as received. Daily files go to R2 (`daily/`). |
| `data/reference/calitp_speeds_204.csv` | Cal-ITP measured speeds (20th, 50th, 80th percentile by time of day), rolled up to the same sections. |
| `data/sections.csv`, `data/feed_versions.csv` | Section boundaries; which GTFS version covers which dates. |

Columns of the hourly tables: `hour_start_utc`, `hour_start_local`, `route`, `direction`, `section_id`,
`speed_mph`, `travel_time_min`, `length_mi`, `n_trips`, `source`, `feed_version`.

```python
import pandas as pd
h = pd.read_parquet("data/hourly")                      # all years
pm = h[(h.section_id == "corridor") & (h.route == "204")]
```

## Other corridors and sources (in progress)

| Path | Contents |
|---|---|
| `corridors/sunset.json` | Sunset Bl / Cesar Chavez Av, Western Av to New High St: path, six sections, project events |
| `data/corridors/sunset/hourly/year=YYYY/sunset_speeds.parquet` | Scheduled hourly speeds for lines 2, 4 and the former 704 since 2018; same columns plus `corridor_id` |
| R2 `gbfs/` | Shared bike and scooter availability snapshots every 10 minutes (Bird, Metro Bike Share), from `worker/gbfs.js` |

See `docs/EXPANSION_PLAN.md` for the before/after plan these support.

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
when collection starts. See "Hosting and ongoing collection" below.

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

## Hosting and ongoing collection

```
LA Metro feed ──every minute──> Cloudflare Worker (cron) ──> R2  raw/<day>/<hour>/*.ndjson.gz
                                                                │
GitHub Actions, hourly:  download last 2 days ──> hourly speeds ──> commit data/observed/
                         daily raw + MDS files ──> R2 daily/ and mds/
                         build site ──> GitHub Pages  and  Cloudflare (site + /api + collector)
```

One workflow, `.github/workflows/publish.yml`, does everything on GitHub's side. It works in two modes:

| | GitHub only | With Cloudflare (recommended) |
|---|---|---|
| Collection | The workflow listens for 20 minutes each hour | Worker listens about 55 seconds of every minute |
| Coverage | About a third of each hour | Continuous |
| Raw archive | Workflow artifacts, kept 90 days | R2, kept indefinitely |
| Site | GitHub Pages | Cloudflare, plus GitHub Pages as a mirror |
| Extra routes | none | `/api/status`, `/api/files?prefix=daily/`, `/api/file/<key>` |

### GitHub Pages (one setting)

Repository Settings > Pages > Source: **GitHub Actions**. Merge this branch into `main`; the next run publishes.
Pages on a private repository needs a paid GitHub plan.

### Cloudflare (one-time, about ten minutes)

```bash
npx wrangler login
npx wrangler r2 bucket create aviary-vermont-speeds-bucket
npx wrangler r2 bucket lifecycle add aviary-vermont-speeds-bucket expire-minute-files raw/ --expire-days 7
python pipeline/build_site.py && npx wrangler deploy      # first deploy; the workflow redeploys after that
```

Then add four repository secrets (Settings > Secrets and variables > Actions):

| Secret | Where it comes from |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare dashboard, account overview |
| `CLOUDFLARE_API_TOKEN` | API token from the "Edit Cloudflare Workers" template |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | R2 > Manage API tokens, Object Read and Write on the bucket |

Notes:

- The minute files under `raw/` expire after 7 days. The workflow has already copied each day into `daily/` and `mds/` by then.
- The Worker stores messages without parsing them, so it uses little CPU. The free plan allows 10 ms of CPU per run, which is tight for
  compressing a minute of messages; the $5 Workers Paid plan removes the risk.
- The site is served at `aviary.herebox.org` (set in `wrangler.jsonc`; Cloudflare creates the DNS record on deploy). More routes go in `worker/index.js`.
- Test locally: `npx wrangler dev --test-scheduled`, then open `http://localhost:8787/__scheduled?cron=*+*+*+*+*`.

## Rebuilding

```bash
pip install -r requirements.txt
git clone --filter=blob:none https://gitlab.com/LACMTA/gtfs_bus.git /tmp/gtfs_bus
python pipeline/backfill_gtfs.py --repo /tmp/gtfs_bus --out data    # about 10 minutes
python pipeline/fetch_calitp.py
python pipeline/collect_realtime.py --minutes 55 --out data/raw     # live pings
python pipeline/build_observed.py
python pipeline/build_site.py                                       # writes _site/
```

The corridor and its sections are defined once, in `pipeline/corridor.py`.

## Known limits

- Bus speeds include boarding time, so they are lower than general traffic speeds on the same street.
- Five of the 130 GTFS commits are unusable (deletions or broken uploads) and are skipped; the neighbouring version fills in. 2019-01-05 has no data.
- Day types on the page are by day of week; holidays are not separated.
- The scheduled workflow only runs once it is on the repository's default branch.
- The Cloudflare deployment has been run locally with `wrangler dev` (collector, storage, routes) but not yet deployed to an account.

## Other sources worth adding

- **Swiftly** (LA Metro's GTFS-realtime vendor): official feed, and historical speed exports if the key allows.
- **Cal-ITP data warehouse**: archived GTFS-realtime for LA Metro since about 2022, which would give a measured hourly history. Access is by request.
- **LADOT ATSAC** signal-system detectors and **INRIX / RITIS** probe speeds for general traffic rather than buses.
