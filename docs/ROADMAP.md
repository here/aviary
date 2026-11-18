# Roadmap and task tracker

The single list of open work for this project. Update the status here when something changes;
`AGENTS.md` describes how the system works, this file says what to do next.

Status values: **done**, **in progress**, **waiting on owner** (needs an account, key, setting or decision),
**next** (ready to start), **later**, **dropped**.

Last updated: 2026-11-18 (A10, A11 added).

## A. Traffic data for other vehicles (explore in this order)

Goal: general traffic, ride-hail, robotaxi, bike and scooter data for the same streets, so each project's
before/after is not bus-only. Facts about programs, prices and terms below are from memory or search summaries
(2026-11-18) and must be verified before relying on them.

| # | Source | What it adds | Access | Status |
|---|---|---|---|---|
| A1 | **Live traffic speed API (HERE or TomTom)** | General-traffic speed on each street segment, collected from now on, beside the bus data | Free developer tier; key goes in the URL | **in progress**: **TomTom collecting since 2026-11-18 04:55 UTC** (22 tiles every 15 minutes). Roll-up built 2026-11-18 (`pipeline/build_traffic.py`, run hourly by the workflow; on the page as a yellow line in the measured-speeds chart). Storage terms still to check. HERE built but unused. See "A1 details" |
| A2 | Strava Metro | Bike and run counts by street segment, history | Free for agencies and approved researchers; apply | next (owner applies) |
| A3 | LADOT data request: Waze for Cities speeds and jams, MDS scooter trips, speed surveys for the study streets | Waze history (LADOT is a partner), scooter trips before/after, measured car speeds | Request to LADOT | next (owner sends) |
| A4 | Metro Bike Share trip history | Station-to-station trips near the corridors, since 2016 | Open CSV | later |
| A5 | GBFS roll-up | Scooter and bike counts near each section from the snapshots already collected (`gbfs/` in R2) | Already collecting | later |
| A6 | CPUC robotaxi and ride-hail filings; California DMV autonomous-vehicle collision reports | Context for the talk (trips, miles, incidents), not street-level speeds | Public filings | later |
| A7 | Commercial probe data: INRIX / RITIS, StreetLight, Replica | Historical general-traffic speeds and trips, which would give a real "before" for Hollywood (built 2024) | Licence, often via a public agency | later (ask LADOT or Metro what they license) |
| A8 | Phone-movement programmes: Spectus, Advan | Anonymised movement for research | Research or nonprofit programmes | later |
| A9 | Open city-level indexes: TomTom Traffic Index | City congestion rankings | Open | dropped for street analysis (too coarse); fine as a slide statistic |
| A10 | **Telraam window counters** | Counts of cars, heavy vehicles, bikes and pedestrians plus car speeds, by segment, counted on the device with no images kept. Fills Fountain Av (no bus data) and adds modes at Lyman Pl to Fountain Av | Buy a unit (price to check) and find hosts; free API key for hourly data | **in progress**: exploring. Overview in `docs/CROWDSOURCED_DATA.md`; site list in `docs/projects/telraam.md`; `pipeline/fetch_telraam.py` written, untested until a key exists. Owner: check Telraam's map for existing LA units, price, hosts, API key |
| A12 | OpenTrafficCam (open-source video counting) | Paths, turning movements, counts by type and speeds from short video studies, e.g. at the Hollywood / Sunset / Hillhurst junction before and after Phase 2 | Open source (GPL-3.0); DIY Raspberry Pi camera or rented units; analysis needs a GPU computer | later: notes in `docs/CROWDSOURCED_DATA.md`. Needs a video-handling policy and a mounting site |
| A11 | Caltrans CCTV still images (District 7) | Anonymous vehicle counts by computer vision, no plate reading, no images kept | Open camera list | later: cameras are almost all on freeways, so little coverage of the study streets; check the list for any surface-street views |
| - | Licence-plate tracking from public cameras | | | dropped: regulated in California (Civil Code 1798.90.5 onward), privacy risk, and public feeds are too low-resolution anyway |
| - | Uber Movement, Apple and Google mobility reports | | | dropped (discontinued) |
| - | Chicago and New York City open ride-hail trip data | Shows what LA does not publish | Open | later (talking point only) |

### A1 details: live traffic speed

- **Provider: HERE Traffic API v7 flow** (recommended). One request returns every road segment in a box, both
  directions, with current and free-flow speed and the segment shape. Three boxes cover all study streets
  (Vermont; Hollywood plus Fountain; Sunset / Cesar Chavez), so collecting every 30 minutes is about
  4,300 requests a month, inside the free 5,000 a month listed on HERE's pricing page (verify).
  Alternative: TomTom Flow Segment Data, one request per point, so many more requests.
- **TomTom option (owner requested a key, 2026-11-18)**: the Orbis Maps Traffic API v2
  ([docs](https://docs.tomtom.com/traffic-api/documentation/tomtom-orbis-maps/v2/product-information/introduction))
  serves flow only as **map tiles** (vector tiles in protobuf, or images); the older per-point "Flow Segment Data" is
  not part of v2. Vector tiles carry, per road piece: `relative_speed` (current over free-flow, 0 to 1),
  `road_category`, `road_closure`, and on request `absolute_speed` (km/h), `part_of_two_way_road` and `openlr`
  (a map-independent location reference). Endpoint
  `https://api.tomtom.com/maps/orbis/traffic/flow/vector/tile/{z}/{x}/{y}?apiVersion=2`, optional `attributes`
  to choose tags. **Key goes in the `TomTom-Api-Key` header** (preferred) or a `key` parameter, so this session can
  test it through the secure form. Coverage: 11 tiles at zoom 13 or 22 at zoom 14 cover all study streets, so every
  15 minutes is about 1,000 to 2,100 requests a day. Unknowns to settle with the first key test: which zoom includes
  arterials like Vermont and Sunset, the exact `attributes` syntax for `absolute_speed`, the free tile quota for
  Orbis, and the storage terms.
- **TomTom working (2026-11-18)**: key tested from this session (header `TomTom-Api-Key`, saved on the `aviary`
  environment) and from the Worker (secret `TOMTOM_API_KEY` from the repository secret). Arterials appear at zooms 12
  to 14. `attributes=tags(absolute_speed,relative_speed,road_category,road_closure,part_of_two_way_road,openlr),roadCategories(primary,secondary,tertiary)`
  works (a `;` separator is rejected). First stored run: 22 of 22 tiles, 3,079 road pieces (primary, secondary,
  tertiary), median 25 km/h at 20:55 local, about 150 KB gzipped per run, about 14 MB a day. Vermont shows as many
  short pieces in both directions (for example 20 to 35 km/h around Wilshire Bl at 20:00).
- **Roll-up built (2026-11-18)**: `pipeline/build_traffic.py` with a built-in tile decoder (`pipeline/mvt.py`, checked
  against `mapbox-vector-tile` on 3,079 features with no differences), so there is no protobuf conflict. Matching: every
  point within 40 m of the street's path and running along it (at least 80% of its length gained along the path);
  duplicates on tile borders dropped. First run: Vermont, Hollywood and Sunset fully covered in both directions;
  Fountain Av misses La Cienega Bl to Crescent Heights Bl until its path is corrected (C2). Output monthly CSVs in
  `data/traffic/` (Vermont) and `data/corridors/<id>/traffic/`, listed in `datapackage.json`.
- **Original roll-up notes**: decode with `mapbox-vector-tile` (pass `y_coord_down=True`, convert tile pixels with
  extent 4096 to longitude and latitude), keep pieces whose shape lies along a corridor path (`polyline.py`
  `locate()`, within about 25 m, direction from the order of points), and write hourly length-weighted speeds per
  section and direction with `source = tomtom_traffic_flow`. **Package conflict**: `mapbox-vector-tile` pulled
  protobuf down to 6.x while `gtfs-realtime-bindings` 3.0 needs protobuf 7.34 or later; pin compatible versions (or
  run the two decoders in separate steps) before adding it to `requirements.txt`.
- **Original plan, for reference**: (1) store it with the secure form as header `TomTom-Api-Key` for host
  `api.tomtom.com` and test zooms 12 to 14 on one Vermont tile; (2) add a TomTom path to `worker/traffic.js` that
  fetches the tile list every 15 minutes and stores the raw tiles in R2 under `traffic/tomtom/` (decoding happens
  later in Python, not in the Worker, to stay inside its CPU limit); (3) repository secret `TOMTOM_API_KEY` for the
  Worker; (4) a roll-up that decodes tiles (`mapbox-vector-tile`), converts tile coordinates to longitude and
  latitude, matches road pieces to corridor sections, and writes hourly general-traffic speeds.
  If both keys arrive, TomTom alone is enough; HERE becomes a cross-check.
- **Terms to check before turning it on**: both providers restrict storing or caching traffic data. Keeping raw
  responses and publishing derived speeds may need a different plan or permission. The owner should read the
  terms and decide.
- **Wiring**: Worker `aviary-traffic-collector` (`worker/traffic.js`, `wrangler.traffic.jsonc`), cron every 30
  minutes, stores gzipped JSON in R2 under `traffic/here/`. Status at `aviary.herebox.org/traffic/status`.
  The key is the repository secret `HERE_API_KEY`; the workflow copies it to the Worker on each deploy.
  The collector does nothing until the key exists.
- **Then**: a roll-up that matches segments to corridor sections (by shape) and writes hourly general-traffic
  speeds in the same columns as the bus tables (`source = here_traffic_flow`), and a line on the page.

## B. Bus speed work

| # | Task | Status |
|---|---|---|
| B1 | Swiftly roll-up into measured speeds | done (2026-11-18) |
| B2 | Swiftly storage plan: roll-up plus expiry rule for `swiftly/`, or accept charges after ~3 months (10 GB free) | later (by February 2027) |
| B3 | Lateness and bunching from Swiftly trip updates and vehicle positions | later (owner: secondary to travel time) |
| B4 | Ask Swiftly whether historical exports are included with the key | waiting on owner |
| B5 | Cal-ITP measured history | **done (2026-11-18)**: Cal-ITP's public bucket `calitp-map-tiles` holds LA Metro speed maps for 14 Wednesdays since October 2024 (no PM peak since September 2025). `pipeline/fetch_calitp_history.py` rolls them up to sections; weekly workflow `calitp-history.yml` refreshes; chart "Measured bus speed over time". Older archive (2022 onward) still internal to Caltrans |
| B6 | Check line 217's implausible 19.2 mph (Gower St to Western Av, 2021) | next |
| B7 | Extend the Hollywood corridor east to Hillhurst Av (Phase 1 east end) | next |
| B8 | Review a full day of focus-segment traversals for bad passes (GPS jumps, layovers) | next |

## C. Corridors and projects

| # | Task | Status |
|---|---|---|
| C1 | Verify project facts (extents, dates) against LADOT, West Hollywood and Metro pages | next (sources in `docs/projects/`, `docs/EXPANSION_PLAN.md`) |
| C2 | Correct `corridors/fountain.json` coordinates (currently approximate) | next |
| C3 | Collisions before/after for each street | moved to E1 (CCRS replaces the LAPD file, which stopped in March 2025) |
| C4 | Before/after panel on the page (treated versus control) | later |
| C5 | Lane-closure data (WZDx-style) from BOE / LADOT permits to flag hours affected by work zones | later |

## E. Safety, incidents and conditions (queued 2026-11-18)

Assessment, with sources checked: [`docs/projects/safety_and_incident_data.md`](projects/safety_and_incident_data.md).

| # | Item | Source | Status |
|---|---|---|---|
| E1 | Collisions per section and year (severity, weather, lighting, road surface) | CCRS on data.ca.gov: open, 2016 to present, includes LAPD, lat/lon. First check why LAPD counts drop from 2016 to 2024 | queued |
| E2 | Traffic incidents (accidents, closures, roadworks) as an hourly flag per section | TomTom Incident Details v5 with the existing key; present-only, so collect every 15 minutes from now on | queued (do soon: history is not recoverable) |
| E3 | Hourly weather and daylight to compare speeds under different conditions | NOAA ASOS (downtown USC, LAX); host to be allowed | queued |
| E4 | Emergency response travel time near each corridor | LAFD Station Response Metrics (monthly per station, 2016 to 2026-09); LA County Fire for Fountain Av needs a request | queued |

## D. Operations

| # | Task | Status |
|---|---|---|
| D1 | Watch that scheduled workflow runs keep firing (GitHub drops some); a full day without a run loses minute files | ongoing |
| D2 | GBFS: expiry or compaction for `gbfs/` | later |
| D3 | Lime GBFS feed (404) | later |
| D4 | Rename "Vermont" leftovers (`aviary-vermont-speeds` Worker and bucket, `vermont.html` artifact) if wanted | later (owner decision) |
