# Roadmap and task tracker

The single list of open work. `AGENTS.md` describes how the system works; this file says what to do next;
`meta/status/` holds short end-of-session summaries. Update the status here when something changes.

Status values: **in progress**, **next** (ready to start), **waiting** (on the owner, a date or data), **later**,
**dropped**. Finished items move to "Done" at the bottom with their date.

Last updated: 2026-11-19.

## Up next (short list)

1. **E1** Collisions from CCRS (top-level requirement: incidents on every stretch, over time; design in
   `docs/INCIDENTS.md`). E2 live incidents started 2026-11-19.
2. **C12** Review Olympic Bl against Pico Bl on **2026-11-26**, then decide on control streets for every project.
3. **C2 / C13** Fix Fountain Av's path and improve HERE coverage on Fountain Av and Westwood Village.
4. **E5** Delay columns in the traffic files.
5. **B2** Swiftly storage plan, due before February 2027 (R2's 10 GB free tier).

## A. Traffic data for other vehicles

Facts about programmes, prices and terms are from search summaries (2026-11-18); verify before relying on them.

| # | Source | What it adds | Status |
|---|---|---|---|
| A1 | Live traffic speed (TomTom, HERE) | General-traffic speed per section | **in progress**: both collecting and on the page (see Done). Open: compare TomTom with HERE after a week; read both providers' storage and redistribution terms (owner) |
| A2 | Strava Metro | Bike and run counts by street segment, with history | waiting (owner applies; free for agencies and researchers) |
| A3 | LADOT data request: Waze for Cities, MDS scooter trips, speed surveys | Waze history, scooter trips, measured car speeds | waiting (owner sends) |
| A4 | Metro Bike Share trip history | Station-to-station trips near the streets since 2016 (open CSV) | later |
| A5 | GBFS roll-up | Scooter and bike counts near each section from `gbfs/` snapshots already collected | later |
| A6 | CPUC robotaxi and ride-hail filings; DMV autonomous-vehicle collision reports | Context for the talk, not street-level | later |
| A7 | INRIX / RITIS, StreetLight, Replica | Historical traffic speeds: a real "before" for Hollywood | later (ask LADOT or Metro what they license) |
| A8 | Spectus, Advan | Anonymised movement, research programmes | later |
| A10 | **Telraam** window counters | Cars, heavy vehicles, bikes, pedestrians and car speeds; fills Fountain Av | **in progress**: `docs/CROWDSOURCED_DATA.md`, `docs/projects/telraam.md`; `pipeline/fetch_telraam.py` untested until a key exists. Owner: check existing LA units, price, hosts, API key |
| A11 | Caltrans CCTV stills (District 7) | Anonymous counts by computer vision | later (cameras are almost all on freeways) |
| A12 | OpenTrafficCam | Turning movements and speeds from short video studies | later (needs a video policy and a mounting site) |
| - | Chicago / New York City open ride-hail trip data | What LA does not publish (talking point) | later |
| - | TomTom Traffic Index | City-level congestion | dropped for streets (slide statistic only) |
| - | Licence-plate tracking from public cameras | | dropped (California Civil Code 1798.90.5 onward, privacy, low resolution) |
| - | Uber Movement; Apple and Google mobility reports | | dropped (discontinued) |

## B. Bus speed work

| # | Task | Status |
|---|---|---|
| B2 | Swiftly storage: roll-up plus expiry rule for `swiftly/`, or accept charges (~3.5 GB a month; 10 GB free) | next (before February 2027) |
| B3 | Lateness and bunching from Swiftly trip updates and vehicle positions | later (owner: secondary to travel time) |
| B4 | Ask Swiftly whether historical exports come with the key | waiting (owner) |
| B6 | Check line 217's implausible 19.2 mph (Gower St to Western Av, 2021) | next |
| B7 | Extend the Hollywood corridor east to Hillhurst Av (Phase 1 east end) | next |
| B8 | Review a full day of focus-segment traversals for bad passes (GPS jumps, layovers) | next |

## C. Streets and projects

| # | Task | Status |
|---|---|---|
| C1 | Verify project facts (extents, dates) against LADOT, West Hollywood and Metro pages; their pages are JavaScript-rendered and LADOT is blocked from the session, so the owner may need to paste text | next |
| C2 | Correct `corridors/fountain.json` (a flat line at 34.0943; Fountain Av runs at about 34.094 to 34.096). TomTom's road geometry can supply the path | next |
| C14 | Project map snapshots under the street picker, with a link to each project page | **in progress**: link for every street; maps for Vermont (Metro), Fountain (West Hollywood), Pico/Olympic (drawn by this project over OpenStreetMap, 2026-11-19) and Hollywood (LADOT Phase 2 intersection design and phase map, with a project description, from owner-supplied graphics, 2026-11-20). Projects can carry a `description` (paragraphs) in `corridors/<id>.json`. LADOT's own map for Pico (Sunset East and Westwood added 2026-11-20 from owner-supplied graphics; Westwood's shows the project ends near Pico Bl, so its S4 is outside it) are live ArcGIS maps: snapshot them once `js.arcgis.com`, the Esri basemap hosts and `salivablestreetstrapi.blob.core.windows.net` are allowed, or from owner screenshots |
| C15 | Higher-resolution project graphics: maps are shown no larger than their files, so small ones stay small. Find larger versions (owner): Hollywood phase map 548 px and intersection design 846 px, Sunset timeline map 780 px and proposed design 788 px, Vermont BRT map 1,100 px, Westwood features map 1,258 px. Aim for 1,400 to 2,000 px wide | next (owner) |
| C4 | Before/after panel on the page (treated against control) | later |
| C5 | Work-zone flags from BOE / LADOT permits (WZDx-style) | later |
| C8 | Traffic-only section for Pico, Bonnie Brae St to Figueroa St (line 30 detours via Olympic), skipped by the bus roll-ups | next |
| C9 | Pico against Olympic difference-in-differences on the page once construction starts | later |
| C11 | Big Blue Bus feeds for Westwood south of Santa Monica Bl (needs its host on the allowlist and a collector change) | later |
| C12 | Control streets for every project | waiting (until 2026-11-26). Review Olympic against Pico (bus GPS and TomTom per section, direction, hour): does it track Pico before construction, and is the data complete? If yes, add one parallel untreated street per project with the same cross streets. Candidates: Vermont → Normandie or Western; Hollywood → Franklin or Santa Monica Bl; Sunset / Cesar Chavez → Beverly Bl / 1st St; Westwood → Sepulveda or Overland; Fountain → Santa Monica Bl or Romaine St. Prefer Metro service; check the tile cost in `docs/FREE_TIERS.md`. If not, record why and choose differently (a matched stretch of the same street, or several averaged controls) |
| C13 | Improve HERE coverage on Fountain Av (~8%) and Westwood Village (~25%) | next. Cheapest first: (1) fix Fountain's path (C2) and widen its HERE radius (40 m now); (2) keep links with confidence 0.7 or lower in a separate flagged column if that is where the gaps are; (3) request `functionalClasses` 4 and 5; (4) last resort: HERE `deepCoverage`, billed separately |

## D. Operations

| # | Task | Status |
|---|---|---|
| D0 | Free-tier usage (`docs/FREE_TIERS.md`). Owner: check the TomTom dashboard usage counter and whether a payment method is attached (and the same for HERE) | ongoing |
| D1 | Scheduled runs are unreliable: from 2026-11-20 17:00 to 2026-11-22 00:30 UTC GitHub ran "Collect and roll up" only 6 times instead of about 31 (gaps of 4 to 8 hours). No data is lost while gaps stay under the two-day download window (R2 raw/ keeps 7 days), but the page goes stale | ongoing; see D6 |
| D6 | Trigger "Collect and roll up" hourly from the traffic Worker's cron (minute 25, `workflow_dispatch` via the GitHub API) | **done (2026-11-22)**: first dispatch at 10:25 UTC returned 204 and started run 11; GitHub's own schedule stays as a backup. Token `GH_DISPATCH_TOKEN` expires on the date the owner chose: renew it then |
| D2 | GBFS: expiry or compaction for `gbfs/` | later |
| D3 | Lime GBFS feed (404) | later |
| D4 | Rename "Vermont" leftovers (`aviary-vermont-speeds` Worker and bucket) if wanted | later (owner decision) |
| D5 | Cut R2 reads: the hourly workflow re-downloads two days of minute files every run (~4.3 million reads a month of 10 million free) | later |

## E. Incidents, safety and conditions

**Top-level requirement (2026-11-19)**: traffic incidents on each stretch, over time and ongoing: delays, collisions
by severity (minor, serious, fatal) and who was involved (pedestrian, bicyclist, vehicle; child or adult). The data
points and storage design are in [`docs/INCIDENTS.md`](INCIDENTS.md); the source survey is in
[`docs/projects/safety_and_incident_data.md`](projects/safety_and_incident_data.md).

| # | Item | Source | Status |
|---|---|---|---|
| E1 | Collisions per section: severity (K, A, B, C, O), traveller type, age band, conditions; weekly refresh re-fetching the last 90 days | CCRS on data.ca.gov (open, 2016 to present, includes LAPD). First check why LAPD counts drop from 2016 to 2024 | next |
| E2 | Live incidents per section (type, size, delay, first and last seen) | TomTom Incident Details: one box over all streets every 20 minutes (~2,160 of the free 2,500 a month) | **in progress**: collecting since 2026-11-19 19:37 UTC, rolled up hourly (`pipeline/build_incidents.py`). Next: show on the page (E6); review matching after a week |
| E7 | Headline fatality numbers (United States, City of Los Angeles by year and year to date) | **done (2026-11-19)**: "Traffic deaths" panel at the top of the page, refreshed daily from CCRS; national from NHTSA by hand. Next: update the national CSV when NHTSA publishes 2025 final figures |
| E5 | Delay columns: `delay_min` (travel time minus free-flow time) in the traffic CSVs, and bus minutes against the timetable | Existing TomTom, HERE and bus data | next |
| E6 | Incidents on the page | **in progress**: TomTom incidents shown as triangles on the hourly chart (with tooltip counts by type) and summarised per street and section in "Traffic incidents and deaths", just above Data sources (2026-11-19). Next: collisions and injuries per street once E1 exists (by severity and traveller type, on the same section) |
| E3 | Hourly weather and daylight | NOAA ASOS (downtown USC, LAX); host to be allowed | later |
| E4 | Emergency-response travel time near each street | LAFD Station Response Metrics (monthly per station); LA County Fire for Fountain needs a request | later |

## Done

| When | What |
|---|---|
| 2026-11-17 | Vermont Av scheduled speeds from GTFS history (2016 on); Worker collector, R2, hourly workflow, site at aviary.herebox.org and GitHub Pages; Hollywood, Sunset and Fountain added; GBFS collector |
| 2026-11-18 | Swiftly collected (from 01:28 UTC) and rolled into measured speeds (B1); TomTom flow tiles collected (from 04:55 UTC) with its own tile decoder and roll-up; Cal-ITP measured history from the public speed-map bucket, weekly refresh (B5); crowdsourced-data and safety-data surveys; workflow push race fixed; actions on Node 24; page redesign (menus, projects, data sources) |
| 2026-11-19 | TomTom incidents collected every 20 minutes and rolled up per section (E2 started); traffic-deaths panel (E7); incident data points designed (`docs/INCIDENTS.md`) |
| 2026-11-19 | Pico Bl (C6) with Olympic Bl as its control (C7); Westwood Bl (C10); free-tier record (`docs/FREE_TIERS.md`); HERE flow with the corridor filter, rolled up and shown dashed beside TomTom; HERE documentation MCP server; street-strip alignment fix; social links |
| moved | C3 collisions → E1 |
