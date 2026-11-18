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

Added 2026-11-17 (later the same day):

- **Sunset / Cesar Chavez corridor** (`corridors/sunset.json`): scheduled speeds for lines 2, 4 and the former 704,
  2018-01-01 to 2026-11-15, 1.4M rows in `data/corridors/sunset/hourly/` (Parquet only, extra `corridor_id` column).
  Built by `pipeline/backfill_corridor.py` using `pipeline/polyline.py` (distance along a path). Not on the page yet.
  Line 2 left Sunset east of Alvarado around 2021, so sections S4 to S6 have line 2 data only to 2021.
- **Bus collector** now records lines 2 and 4 as well (`ROUTES`).
- **GBFS collector**: Worker `aviary-gbfs-collector` (`worker/gbfs.js`, `wrangler.gbfs.jsonc`), every 10 minutes,
  snapshots to R2 under `gbfs/`. Working: Bird (about 3,100 vehicles in the study box) and Metro Bike Share
  (145 stations). Returning nothing in the box: Lyft, Spin, Veo. **Lime is missing**: its feed address 404s.
  Maintenance routes: `aviary.herebox.org/gbfs/status`, `/gbfs/run`, `/gbfs/discover`. No roll-up script yet,
  and `gbfs/` has no expiry rule or daily compaction yet (about 290 snapshots a day).
- **Measured roll-up for path corridors**: `pipeline/build_observed_corridor.py` writes hourly section speeds and,
  for the short focus segments, one row per bus traversal plus an hourly summary, under
  `data/corridors/sunset/observed/`. Focus segments F1 (Hillhurst / Virgil junction to Fountain Av), F1a (junction
  zone) and F1b (rest) are defined in `corridors/sunset.json`. Pings arrive about every 6 seconds, so crossing
  times are well resolved. Only about 20 minutes of late-night data existed when this was written.
  `pipeline/fetch_archive.py` downloads archived files from the public API without keys. The workflow runs the
  roll-up for every file in `corridors/`.
- Project status notes and the priority segment (Lyman Pl to Fountain Av) are in `docs/EXPANSION_PLAN.md`.

Cloudflare: account ID `4c63641622d8786f6373a2430b970c25`, which owns the `herebox.org` zone.
All Cloudflare resource names are prefixed `aviary-`. Use `aviary.herebox.org` for anything needing DNS.

## In flight when the session ended (2026-11-17, about 08:00 UTC)

Three background agents were started just before the owner's usage window closed. Their work may be partial.
Check `git log` and `git status` first; each was told to commit and push only its own files.

| Agent task | Files it owns | Done when |
|---|---|---|
| Hollywood Bl corridor (LADOT Hollywood Blvd Safety and Mobility Project, Gower St to Hillhurst Av) | `corridors/hollywood.json`, `data/corridors/hollywood/` | JSON has path, sections, routes, events; scheduled backfill since 2018 exists |
| Hollywood project research | `docs/projects/hollywood-blvd.md` | Status, extents, dates, what was built, sources |
| Fountain Av street safety project research (no bus) | `docs/projects/fountain-av.md`, `corridors/fountain.json` | Status, extents, dates, sources; corridor file has endpoints and events, no routes |

Outcome so far: both research documents are finished and pushed. Findings that change the plan:

- **Fountain Av's road diet is the City of West Hollywood's project** (La Cienega Bl to La Brea Av, 1.8 mi, four lanes
  to two, approved 2025-09-15), not LADOT's. Construction was expected late 2026 and is not confirmed as started.
  LADOT's only work found on Fountain is a 2023 westbound bike lane, Vermont Av to Kingsley Dr.
- **"No bus on Fountain" holds only for the West Hollywood part.** LADOT DASH Hollywood runs on Fountain in Hollywood.
- **Hollywood Phase 1** opened August 2024; no published before/after data was found. Baseline cited by LADOT:
  53 severe-injury and fatal collisions in the project area, 2010 to 2019.
- Both documents are built from search-result summaries only; no source page was opened. Verify before quoting.
- `corridors/fountain.json` has approximate coordinates (latitude held constant) and must be corrected before use.
- **Hollywood corridor** (`corridors/hollywood.json`, Highland Av to Vermont Av, four sections): scheduled speeds for
  lines 180, 217 and 780, 2018-01-01 to 2026-11-16, 1.2M rows in `data/corridors/hollywood/`. The agent building it was
  cut off by a usage limit after the backfill finished; the output was checked and committed by the main session.
  Caveats: the corridor stops at Vermont Av, so it does not reach Hillhurst Av (the Phase 1 east end); 780 data ends
  in 2021; line 217 shows an implausible 19.2 mph on Gower St to Western Av in 2021, worth checking before quoting.
- **Charts page** now has a Street picker (Vermont, Hollywood, Sunset), project-date markers on the time series, an
  events list per street, and a "Measured through the next project site" table for the Sunset focus segments.
  Corridors without bus data (Fountain Av) are listed in the notes.

If any of these is missing or half-done, redo it; nothing else depends on them yet. Owner's reference pages:
`https://ladotlivablestreets.org/projects/hollywood-blvd` and `/projects/sunset` (JavaScript-rendered; use a
browser or web search, a plain fetch returns an empty shell).

Session constraints worth knowing: the cloud environment `aviary` has a limited network allowlist
(Cloudflare API, api.metro.net, gitlab.com, Caltrans GIS, data.ca.gov, aviary.herebox.org). data.lacity.org,
LADOT sites and operator sites are blocked there; widen the allowlist in the environment settings or work
from a local machine. The owner could not approve environment changes from a phone.

## Status update 2026-11-18

- **The hourly workflow works with R2.** Run 7 (manual, 2026-11-18 00:18 UTC) downloaded the minute files from R2,
  rolled them up, committed observed speeds, and wrote permanent daily files to R2 (`daily/` and `mds/` for
  2026-11-17 and 2026-11-18). The 7-day expiry on `raw/` is now safe as long as the workflow keeps running.
- **Full Cloudflare deploy from CI works** (run 9, 2026-11-18 00:54 UTC) after the owner added account-level Workers
  Scripts and R2 edit permissions to the token. Both Workers (`aviary-vermont-speeds`, `aviary-gbfs-collector`) were
  redeployed from `main`, replacing the interim bundled-page Worker. `aviary.herebox.org/data/` and
  `/datapackage.json` now serve the archive. The deploy step stays `continue-on-error` so a future token problem
  cannot block collection or Pages; check that step's result, not just the run's.
- **Default branch is `main`**; Actions is enabled.
- **GitHub Pages**: the workflow's Pages job deployed once (run 6). A separate `pages-build-deployment` workflow
  also runs, which means Pages may be set to "Deploy from a branch". It should be set to "GitHub Actions"
  (Settings > Pages) so the built `_site/` is what gets served.
- **Scheduled runs are sparse**: only a few `schedule` runs fired on 2026-11-17 although the cron is hourly.
  GitHub delays and drops scheduled runs under load. Each run downloads two days of files, so a missed hour is
  harmless; a full day without runs is not. Watch it.

## Swiftly (working 2026-11-18)

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
9. **Expansion to before/after road-diet corridors** (Fountain, Hollywood, Sunset / Cesar Chavez): plan in
   `docs/EXPANSION_PLAN.md`. The collector already archives lines 2 and 4 for it.

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
