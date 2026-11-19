# Handoff notes for agents

Read `README.md` for what the project is and the published links. This file explains how the system works and
what is easy to get wrong. **Open work and its status live in [`docs/ROADMAP.md`](docs/ROADMAP.md)**; update that
file when you finish or start something, and update "Current state" below when the system itself changes. At the end
of a session, add a short summary to `meta/status/` (see `meta/README.md`).

## Project in one paragraph

A demo for the CoMotion LA conference: hourly bus speeds on Los Angeles streets being redesigned (Vermont Av,
Hollywood Bl, Sunset Bl / Cesar Chavez Av, Pico Bl with Olympic Bl as its untreated control, Westwood Bl; Fountain Av tracked without bus data), as a time-series page plus an
archive in standard formats (Parquet, CSV, Frictionless data package, OMF MDS 2.0 telemetry). The long series is
*scheduled* speed rebuilt from LA Metro's GTFS git history (Vermont since 2016, the others since 2018). Measured
speed comes from bus GPS collected every minute since November 2026 (LA Metro's public feed and Swiftly), so each
upcoming project gets a measured "before".

## Where things are

| Path | What |
|---|---|
| `docs/ROADMAP.md` | Task tracker: up-next list, open items by area, done log |
| `meta/status/` | One short status note per working session (newest last); read the latest first |
| `docs/EXPANSION_PLAN.md` | Before/after method and project status notes |
| `docs/FREE_TIERS.md` | Free allowances of every API and service, current usage and headroom; update when adding a street, tile box or collector |
| `docs/CROWDSOURCED_DATA.md` | Community-collected data (Telraam first) and why it matters here |
| `docs/projects/` | Sourced research notes per project (Hollywood Bl, Fountain Av, Pico Bl, Westwood Bl) and per data source being explored (Telraam) |
| `corridors/*.json` | Street definitions: path, sections, bus lines, project dates, focus segments |
| `pipeline/` | Backfills, roll-ups, data package and site builders (see each file's docstring) |
| `worker/` | Cloudflare Workers: bus collector + site + API (`index.js`), GBFS (`gbfs.js`), traffic speeds (`traffic.js`) |
| `site/template.html` | The charts page (single file; data inlined at build) |
| `.mcp.json` | MCP servers for Claude Code: `here-docs` (HERE documentation, `https://docs.here.com/mcp`, public, no key). Search HERE docs and API specs (tools `search`, `fetch`, `list-specs`, `list-endpoints`, `search-endpoints`, `get-endpoint`, `get-server-variables`); it does not call HERE APIs. `docs.here.com` is on the `aviary` environment allowlist (2026-11-19) and the server answers from the session; its tools load in sessions started after that. Without them, call it with curl: POST JSON-RPC `tools/call` to `https://docs.here.com/mcp` with `Accept: application/json, text/event-stream` (no session needed) |
| `.github/workflows/publish.yml` | Hourly: collect, roll up, commit, rebuild package and site, deploy to Cloudflare and Pages |

## Current state (2026-11-19)

| Item | State |
|---|---|
| Site | Live at `https://aviary.herebox.org` (Cloudflare Worker with static assets) and `https://here.github.io/aviary/` (Pages, Source = GitHub Actions). Archive under `/data/`, package at `/datapackage.json`, street definitions at `/corridors/` |
| Bus collector | Worker `aviary-vermont-speeds`, every minute: Metro websocket (lines 204, 754, 2, 4) into R2 `raw/` (7-day expiry); Swiftly vehicle positions every minute and trip updates every 15 minutes into `swiftly/` (no expiry). Status: `/api/status`, `/api/swiftly` |
| GBFS collector | Worker `aviary-gbfs-collector`, every 10 minutes into `gbfs/`. Bird and Metro Bike Share working; Lime missing. Status: `/gbfs/status` |
| Traffic-speed collector | Worker `aviary-traffic-collector` (`worker/traffic.js`): TomTom Vector Flow Tiles every 15 minutes (30 zoom-14 tiles) into `traffic/tomtom/` since 2026-11-18 04:55 UTC; HERE flow every 90 minutes (one corridor request per street) into `traffic/here/` since 2026-11-19. Rolled up hourly by `pipeline/build_traffic.py`; on the page as the solid (TomTom) and dashed (HERE) yellow lines. Status `/traffic/status`; `/traffic/run` collects now (`?here=1` adds HERE, 7 requests). Details: "Traffic providers" below |
| Hourly workflow | Downloads two days of pings from R2 (Metro + Swiftly), rolls up measured speeds for every street, commits them, writes permanent daily raw and MDS files to R2 (`daily/`, `mds/`), regenerates `datapackage.json`, builds the site, deploys Workers (step is `continue-on-error`: check it) and Pages. GitHub drops some scheduled runs |
| Scheduled series | Vermont 2016-01-31 onward (`data/hourly/`); Hollywood, Sunset, Pico and Olympic 2018 onward, Westwood June 2021 onward (`data/corridors/<id>/hourly/`). Rebuild needs the GTFS clone; not run by the workflow |
| Measured series | Monthly CSVs: `data/observed/` (Vermont), `data/corridors/<id>/observed/` (with bus-by-bus focus-segment timings for Sunset) |
| Measured bus history (Cal-ITP) | `data/calitp/vermont_calitp_history.csv`, `data/corridors/<id>/calitp/<id>_calitp_history.csv`: median, 20th and 80th percentile bus speeds per section, line, direction and time of day for 13 analysis Wednesdays from 2024-10 to 2026-07, from Cal-ITP's public speed maps. Built by `pipeline/fetch_calitp_history.py`; refreshed weekly by `.github/workflows/calitp-history.yml`. LA Metro's bus feed is named `recPnGkwdpnr8jmHB` (to 2025-07), then base64 of its GTFS address or `recX8JOPmBQM9aWLC` in the file names. Cal-ITP dropped PM Peak after 2025-07; 2024-10 and 2025-01 are partial |
| General-traffic series | Monthly CSVs per street: TomTom `data/traffic/vermont_traffic_YYYY-MM.csv`, `data/corridors/<id>/traffic/<id>_traffic_YYYY-MM.csv`; HERE the same with `_here_traffic_` (speed, free-flow speed, coverage, closures per section and direction) |
| Repository secrets | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` (account Workers + R2 edit, zone `herebox.org`), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `SWIFTLY_API_KEY`, `TOMTOM_API_KEY`, `HERE_API_KEY` (added 2026-11-19; only the API key is used, not the app ID) |
| Cloud session environment `aviary` | Limited network allowlist (Cloudflare API, api.metro.net, gitlab.com, Caltrans GIS, data.ca.gov, aviary.herebox.org, and since 2026-11-18 docs.calitp.org, www.calitp.org, data.lacity.org, here.github.io, storage.googleapis.com, docs.here.com). Network secrets for `api.cloudflare.com`, `api.goswift.ly` (bare `Authorization` header) and `api.tomtom.com` (`TomTom-Api-Key` header). LADOT and operator sites are still blocked; widen it from the environment settings on a computer (the owner cannot approve changes from the phone app) |

Commits: set the repository identity at the start of each session with `git config user.name "mike"` and `git config user.email "mike@herebox.org"`, so the owner is the author and committer; keep the Claude `Co-Authored-By` line in the message. The workflows commit as github-actions[bot].

Cloudflare: account ID `4c63641622d8786f6373a2430b970c25`, which owns the `herebox.org` zone.
All Cloudflare resource names are prefixed `aviary-`. Use `aviary.herebox.org` for anything needing DNS.

Corridor caveats: Fountain Av's road diet is the City of West Hollywood's project (La Cienega Bl to La Brea Av),
not LADOT's, and LADOT DASH runs on the Hollywood part of Fountain; `corridors/fountain.json` coordinates are
approximate. The Hollywood corridor ends at Vermont Av, short of Hillhurst Av. The Pico corridor ends at Bonnie Brae St,
where line 30 leaves Pico, 0.6 mi short of the project's east end at Figueroa St (`docs/projects/pico-bl.md`). `corridors/olympic.json` is a
control street, not a project (`control_for: pico`, line 28, same cross streets); `short_name` sets its picker label. `corridors/westwood.json` runs north to south (`ends`: North, South); Metro buses
cover only Le Conte Av to Santa Monica Bl, and the rest is Big Blue Bus, not collected (`docs/projects/westwood-bl.md`). Research notes in `docs/projects/`
come from search-result summaries; verify before quoting.

## Swiftly

- Key works. Host `api.goswift.ly`; header `Authorization: <key>` with **no** "Bearer" prefix. The session's
  credential form always adds a prefix, so the owner set it as a network secret in the `aviary` environment
  settings (type Bearer, prefix cleared). Limit: 180 requests per 15 minutes.
- Test: `GET https://api.goswift.ly/test-key` returns `{"success":true}`.
- Feeds (protobuf), agency keys `lametro` and `lametro-rail`:
  `/real-time/<agency>/gtfs-rt-vehicle-positions`, `/gtfs-rt-trip-updates`, `/gtfs-rt-alerts`.
  On 2026-11-18 the bus vehicle feed had about 1,700 vehicles (lines 2, 4, 204, 754, 180, 217 all present), 2 s old.
  Route ids match the static GTFS (`204-13201`). Decode with `gtfs-realtime-bindings`.
- Docs: `https://swiftly-inc.stoplight.io/docs/realtime-standalone/` (JavaScript-rendered; automated fetches get 404).
- **Collecting since 2026-11-18 01:28 UTC.** The collector Worker stores Swiftly bus feeds (agency `lametro` only,
  not rail) in R2, unparsed protobuf, gzipped: vehicle positions every minute (`swiftly/vp/`, about 55 KB each) and
  trip updates every 15 minutes (`swiftly/tu/`, about 400 KB each). Status: `aviary.herebox.org/api/swiftly`.
  The workflow sets the Worker secret `SWIFTLY_API_KEY` from the repository secret of the same name on each deploy.
- **Storage**: roughly 115 MB a day, about 3.5 GB a month. `swiftly/` has **no expiry rule** on purpose, because
  nothing rolls it up yet. R2's free tier is 10 GB, so after about three months either add a roll-up plus expiry
  or accept small storage charges.
- **Swiftly feeds the measured speeds (2026-11-18).** `pipeline/swiftly_to_pings.py` decodes `swiftly/vp/`
  snapshots into the same JSON lines as Metro's websocket messages (the two feeds carry identical vehicle records),
  tagged `"source":"swiftly"` and filtered to the study routes (Vermont plus every `corridors/*.json`). The hourly
  workflow downloads two days of snapshots, converts them into `run/raw/swiftly/`, and the existing roll-ups read
  both feeds, dropping duplicates on (vehicle id, timestamp). The daily raw export in R2 (`daily/`) now includes the
  Swiftly records for the study routes.
- What Swiftly adds: every route once a minute, so **Hollywood (lines 180, 217) has measured speeds** for the first
  time, and the other corridors are covered when Metro's websocket drops. Metro's websocket still gives finer
  pings (every few seconds) for 204, 754, 2 and 4, which matters for the short focus segments.
- Page: the "Timetable against measured speeds" chart labels the green points as bus GPS from both feeds; Cal-ITP
  legend entries appear only where Cal-ITP data exists (Vermont line 204).
- **Owner's priorities (2026-11-18)**: overall travel time first. Lateness (schedule adherence) and bunching
  (uneven headways) are secondary, to be kept as possible findings for later. Bunching can be measured from the
  minute-by-minute vehicle positions; lateness needs trip updates or the scheduled times in the static GTFS.

## Traffic providers

- **TomTom** Orbis Maps Traffic API v2, Vector Flow Tiles:
  `GET api.tomtom.com/maps/orbis/traffic/flow/vector/tile/14/{x}/{y}?apiVersion=2&attributes=tags(absolute_speed,relative_speed,road_category,road_closure,part_of_two_way_road,openlr),roadCategories(primary,secondary,tertiary)`
  with header `TomTom-Api-Key`.
  - The attribute list needs commas: a `;` separator is rejected.
  - Arterials appear at zooms 12 to 14; zoom 14 is used.
  - Tiles are stored raw (base64 in one gzipped JSON per run) and decoded later by `pipeline/mvt.py`.
  - Each new street adds 1 to 4 tiles; the tile list comes from the boxes in `worker/traffic.js`.
  - Free allowance: 200,000 tile requests a month; we use about 86,000.
- **HERE** Traffic API v7 flow:
  `GET data.traffic.hereapi.com/v7/flow?in=corridor:{flexible polyline};r=40&locationReferencing=shape&apiKey=...`
  - One request per street, made along its own path. The path is simplified, then encoded by
    `worker/flexpolyline.js`, which reproduces HERE's published examples. URLs must stay under 1,000 characters.
  - Free allowance: 5,000 requests a month. 7 streets every 90 minutes is about 3,400; hourly would be about 5,000, too close.
  - The roll-up keeps live speeds only (confidence above 0.7) and matches each HERE file to its own street only.
  - Coverage is thin on Fountain Av and Westwood Village (roadmap C13).
- **Matching** (both providers):
  - A piece counts when every point is within 40 m of the street's path and at least 80% of its length runs along it.
  - Direction comes from the order of its points.
  - Section speed is the harmonic, length-weighted average; the hourly value is the harmonic mean of the snapshots.
- **Terms**: both providers restrict storing traffic data. We keep raw responses and publish derived hourly speeds;
  the owner still has to read the terms (roadmap A1).

## Data package

- `datapackage.json` is **generated** by `pipeline/build_datapackage.py` from the files that exist; do not edit it by
  hand. The workflow regenerates and commits it each run, so new monthly observed files and new corridors appear
  automatically. Name `aviary-la-street-speeds`, version 0.2.0, profile `data-package`.
- One resource per file; yearly Parquet and monthly CSV files of one dataset share a `group` (e.g. `sunset-hourly`).
  Frictionless rejects a list of paths for these (it treats a list as parts of one file).
- Street definitions `corridors/*.json` are listed as JSON resources and published at `/corridors/` on the site.
- Validated with `frictionless` 2026-11-18: no metadata errors, every CSV matches its schema.

## Things that are easy to get wrong

- **Scheduled is not measured.** Do not describe the 2016-2026 series as traffic speed or observed speed.
  It is distance over timetable running time. Flat stretches (for example 2023 to 2025) mean Metro did not
  re-time the route.
- **Bus speeds include stops.** They sit well below general traffic speeds.
- **OMF fit is partial.** MDS has no transit-bus mode and no roadway-speed table. Only the GPS pings use an
  OMF shape (MDS 2.0 Telemetry); `provider_id` is a placeholder because LA Metro is not a registered MDS
  provider. The hourly table is this project's own schema (`datapackage.json`).
- **Corridor geometry**: Vermont Av is defined in `pipeline/corridor.py` (it runs due north-south, so position is
  latitude); every other street is a path in `corridors/<id>.json` read by `pipeline/polyline.py`. Changing a
  boundary means re-running that street's backfill.
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
  401. Let the workflow deploy anything with static assets. Workers without assets (GBFS, traffic) can be deployed
  from a session with the saved token.
- **Pushing to `main` while a workflow run is working** used to fail that run's data commit (runs 27 and 28,
  2026-11-18). The commit step now rebases onto `main` and retries; on a data-file conflict the run's own data wins.
  Workflow actions are on Node 24 versions (checkout v7, setup-python v7, upload-artifact v7, upload-pages-artifact v5,
  deploy-pages v5).
- **`wrangler login` needs a local browser.** In a cloud session use an API token; in CI use the secret.
- **Traffic tiles are decoded by `pipeline/mvt.py`**, not `mapbox-vector-tile`, which pins an older protobuf than
  `gtfs-realtime-bindings` needs. Tile y runs downwards from the top left; extent is 4096.
- **The built page has no CSS reset**, so `site/template.html` itself carries `[hidden] { display: none !important; }`.
  Without it, elements hidden with the `hidden` attribute (the next-project-site box, the Line control on Fountain Av)
  still render, because `.panel` and `.ctl` set `display`. After editing CSS, check that braces balance: a stray
  `}` silently disables the rule that follows it.
- **Street picker order** is set in `pipeline/build_site.py` (`order = [...]`). A street with no bus data but with
  TomTom traffic data (Fountain Av) is shown with traffic only: no Line control, traffic-based figure and table.
- **Page conventions**: `site/template.html` is a single self-contained file with the data inlined at
  `/*DATA*/null`. Colors are CSS tokens with light and dark values; the four series colors were checked for
  colorblind separation, so do not swap them casually. No external requests except Google Fonts.

## Cal-ITP (measured history) notes

**Checked against Cal-ITP's documentation on 2026-11-18** (`docs.calitp.org/data-infra`):
- The data warehouse (BigQuery, JupyterHub, Metabase, dbt docs at `dbt-docs.dds.dot.ca.gov`) is **internal**: access
  comes with Caltrans Division of Data and Digital Services onboarding, and the docs point staff to the Cal-ITP Slack
  `#services-team` channel for help. There is **no published process for outside requests**, and `www.calitp.org`
  lists no contact email. A request would go through a Caltrans or partner-agency contact, or as a question on the
  public GitHub repository `cal-itp/data-infra`.
- Public outputs: the California Open Data Portal (GTFS schedule data), the Caltrans geoportal (the speeds snapshot
  this project already uses), the analytics portfolio `analysis.calitp.org` (unreachable from the session), and a
  **public Google Cloud Storage bucket `calitp-map-tiles`** that holds the rendered speed maps from their realtime
  analysis tools. It holds LA Metro segment speeds for roughly monthly Wednesdays since October 2024, and is what
  this project uses for measured history.

- **Measured history in use**: the `calitp-map-tiles` bucket (see "Current state"). Its folders are
  `segment_speeds_YYYY-MM-DD/`, and only `new_speedmap` files are used.
- **One-day snapshot**: `pipeline/fetch_calitp.py` pulls line 204 from the Caltrans geoportal (ArcGIS FeatureServer
  `Speeds_by_Stop_Segments`) into `data/reference/calitp_speeds_204.csv`. Re-running overwrites it.
  - `route_name` is a string (`'204'`).
  - Filter the agency with `agency LIKE 'Los Angeles County Metro%'`.
  - Skip features without geometry.
  - `direction_id` 0 is northbound.
- **Sanity check**: midday on Vermont is about 8.7 mph measured against 8.6 mph scheduled.
- **If warehouse access is ever granted**:
  - Write a loader that turns its vehicle positions into the ping columns `build_observed.py` uses (vehicle id, trip
    id, start date, route, timestamp, lat, lon), and reuse `hourly()` (`source = gtfs_realtime_observed`).
  - Alternatives for the same history: LA Metro's own vehicle-location archive, or Swiftly exports (roadmap B4).

## Other sources considered

- **LADOT ATSAC** signal-system detectors and **INRIX / RITIS** probe data: general traffic speed rather than
  buses. Not public; would need an agreement.
- **Caltrans PeMS**: freeways only, so not useful for Vermont Av.
- **Uber Movement**: discontinued.
