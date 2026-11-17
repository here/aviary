# Handoff notes for agents

Read `README.md` first for what the project is, the data layout and the setup commands.
This file records the current state, what is blocked, and things that are easy to get wrong.
Update the "Current state" and "Open work" sections when you change either.

## Project in one paragraph

A demo for the CoMotion LA conference: hourly bus speeds on Vermont Av in Los Angeles
(LA Metro lines 204 Local and 754 Rapid), 2016 to today, as a time-series page plus an
archive in standard formats (Parquet, CSV, Frictionless data package, OMF MDS 2.0 telemetry).
The long series is *scheduled* speed rebuilt from LA Metro's GTFS git history. Measured speed
comes from a live GPS collector that has only just started, and from a Cal-ITP snapshot.

## Current state (2026-11-17)

| Item | State |
|---|---|
| Hourly schedule archive, 2016-01-31 to 2026-11-16 | Built and committed (`data/hourly/`, about 2.2M rows) |
| Observed archive | 13 section-hours from one 20-minute sample (`data/observed/vermont_observed_2026-11.csv`) |
| Charts page | Works; built by `pipeline/build_site.py` into `_site/` (not committed) |
| `https://aviary.herebox.org` | Live, **interim**: charts page bundled inside the Worker, plus the real collector and `/api` routes. No archive downloads under `/data/` yet |
| Cloudflare Worker `aviary-vermont-speeds` | Deployed 2026-11-17 from a cloud session: `worker/index.js` wrapped to serve the bundled page instead of static assets. Cron every minute. First capture not yet confirmed at time of writing; check `/api/status` |
| R2 bucket `aviary-vermont-speeds-bucket` | Created, with a 7-day expiry rule on `raw/` |
| GitHub Actions workflow `publish.yml` | Written, YAML parses, **never run** |
| GitHub Pages | Not enabled; URL will be `https://here.github.io/aviary/` |
| Worker in `worker/index.js` | Tested locally with `wrangler dev` only (collector, R2, routes all worked) |

Cloudflare: account ID `4c63641622d8786f6373a2430b970c25`, which owns the `herebox.org` zone.
All Cloudflare resource names are prefixed `aviary-`. Use `aviary.herebox.org` for anything needing DNS.

## Open work, in order

1. **Confirm the collector is writing**: `https://aviary.herebox.org/api/status` should show a recent `at`
   and `/api/files?prefix=raw/` should list minute files.
2. **Full Worker deploy**: `python pipeline/build_site.py && npx wrangler deploy` from the repo root, or let
   the workflow do it once the secrets exist. This replaces the interim Worker with the static-assets
   version, which adds the archive downloads under `/data/`.
3. `main` exists and is the branch the workflow watches. Keep it the default branch.
4. **Repository secrets**: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
   (see README for where each comes from). Without the R2 pair the workflow falls back to sampling
   the feed itself for 20 minutes an hour.
5. **GitHub Pages**: Settings > Pages > Source: GitHub Actions.
6. **Watch the first workflow runs.** The R2 download/upload steps and the CI Cloudflare deploy are untested.
7. **Swiftly**: the owner has requested an API key for LA Metro's official GTFS-realtime feed. When it
   arrives, add Swiftly as a second collector source and ask whether historical exports are included.
8. **Measured history**: see "Cal-ITP" below.

## Things that are easy to get wrong

- **Scheduled is not measured.** Do not describe the 2016-2026 series as traffic speed or observed speed.
  It is distance over timetable running time. Flat stretches (for example 2023 to 2025) mean Metro did not
  re-time the route.
- **Bus speeds include stops.** They sit well below general traffic speeds.
- **OMF fit is partial.** MDS has no transit-bus mode and no roadway-speed table. Only the GPS pings use an
  OMF shape (MDS 2.0 Telemetry); `provider_id` is a placeholder because LA Metro is not a registered MDS
  provider. The hourly table is this project's own schema (`datapackage.json`).
- **Corridor geometry lives in one place**: `pipeline/corridor.py`. Vermont Av runs due north-south, so
  position along the street is latitude. Changing a boundary means re-running the backfill.
- **Backfill takes about 10 minutes** and needs a clone of `gitlab.com/LACMTA/gtfs_bus`
  (`--filter=blob:none` is fine). Five of the 130 GTFS commits are unusable and are skipped by design.
- **Metro realtime**: the REST vehicle endpoints return empty lists; use the websocket
  `wss://api.metro.net/ws/LACMTA/vehicle_positions/204,754`. No key needed. Messages repeat, so
  de-duplicate on (vehicle id, timestamp).
- **Observed files merge, they do not append.** `build_observed.py` replaces an hour's row when it is
  re-measured. One CSV per local month.
- **Do not commit `_site/`, raw `.ndjson`, or daily telemetry.** Daily raw and MDS files belong in R2
  (`daily/`, `mds/`); minute files under `raw/` expire after 7 days.
- **Cloudflare free plan** allows 10 ms CPU per cron run, which is tight for gzipping a minute of messages.
- **Claude cloud sessions cannot upload Worker static assets.** The session proxy overwrites the one-time
  upload authorization with the saved API token, so `wrangler deploy` with an `assets` directory fails with
  401. Deploy the full Worker from GitHub Actions or a local machine. (That is why the interim Worker exists.)
- **`wrangler login` needs a local browser.** In a cloud session use an API token; in CI use the secret.
- **Page conventions**: `site/template.html` is a single self-contained file with the data inlined at
  `/*DATA*/null`. Colors are CSS tokens with light and dark values; the four series colors were checked for
  colorblind separation, so do not swap them casually. No external requests except Google Fonts.

## Cal-ITP (measured history) notes

*The access process below is from memory and has not been verified against Cal-ITP's site. Check it first.*

- **What exists publicly**: "Average Transit Speeds by Stop" and "Average Transit Speeds by Route" on
  data.ca.gov, served from `caltrans-gis.dot.ca.gov` (ArcGIS FeatureServer, layers `Speeds_by_Stop_Segments`
  and `Speeds_by_Route_Time_of_Day`). They give 20th/50th/80th percentile speeds by time-of-day period for
  a single recent weekday. `pipeline/fetch_calitp.py` pulls line 204 and rolls it up to our sections
  (`data/reference/calitp_speeds_204.csv`). It is a snapshot, not a history; re-running overwrites it.
- **Query quirks**: `route_name` is a string (`'204'`); filter the agency with
  `agency LIKE 'Los Angeles County Metro%'`; some features have no geometry and must be skipped;
  `direction_id` 0 is northbound for the 204.
- **Agreement with our series**: on the current timetable, midday is about 8.7 mph measured against
  8.6 mph scheduled for the corridor. Useful as a sanity check after any method change.
- **What would give a measured history**: Cal-ITP (California Integrated Travel Project, Caltrans) archives
  every California agency's GTFS-realtime feeds, including LA Metro vehicle positions, in a BigQuery
  warehouse. The archive is believed to start around 2022. It is not openly downloadable; access is thought
  to be by request for Caltrans staff and partners.
- **Where to ask** (unverified): `hello@calitp.org`; documentation at `docs.calitp.org/data-infra`.
- **What to ask for**, any one of: read access to the vehicle-position tables; a one-time export for LA
  Metro routes 204 and 754 as far back as the archive goes; or hourly/daily segment speeds for those routes
  if already computed.
- **If access is granted**: write a loader that turns their vehicle positions into the same ping columns
  `build_observed.py` uses (vehicle id, trip id, start date, route, timestamp, lat, lon), then reuse
  `hourly()` so historical and live measured rows share one method and one schema
  (`source = gtfs_realtime_observed`).
- **Alternatives for the same history**: LA Metro's own vehicle-location archive (ask Metro's data team),
  or historical exports through Swiftly if the key allows.

## Other sources considered

- **LADOT ATSAC** signal-system detectors and **INRIX / RITIS** probe data: general traffic speed rather than
  buses. Not public; would need an agreement.
- **Caltrans PeMS**: freeways only, so not useful for Vermont Av.
- **Uber Movement**: discontinued.
