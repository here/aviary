# Expansion plan: before/after road diets and safe-streets projects

Status: plan only, written 2026-11-17. Nothing here is built except item 0.
Facts marked *(verify)* are from memory and must be checked before they appear on a page.

## Goal

Extend the Vermont Av demo into a before/after comparison for street redesigns:

| Corridor | Treatment | Bus | Role |
|---|---|---|---|
| Fountain Av | Road diet | none | Treated, no transit data |
| Hollywood Bl, safe-streets section | Safe-streets installation *(verify extent and opening date)* | *(verify which lines)* | Treated |
| Hollywood Bl / Sunset, next section past the Vista Theatre | Not yet treated | Line 2 | Control, and next-phase baseline |
| Sunset Bl east into Cesar Chavez Av | Focus corridor | Line 4 | Treated or baseline *(confirm with owner)* |
| Vermont Av | none | 204, 754 | Existing reference |

The question each page answers: did speed, reliability and safety change after the redesign, compared
with a similar street that was not changed?

## Project status found so far (web search summaries, 2026-11-17; re-check with LADOT)

- **Hollywood Bl Safety and Mobility Project**: Gower St to Hillhurst Av. Construction began August 2024.
  This is the built "safe streets" section and the main before/after event.
- **Hollywood project Phase 2**: Sunset Bl from Hillhurst Av to Fountain Av, in front of the Vista Theatre
  (line 2). Not yet installed. Use as control now and as baseline for its own before/after later.
- **Hollywood Phase 1 result (LADOT fact sheet, no numbers found)**: lower average speeds on Hollywood Bl and
  more cycling and walking. No published before/after study was found, which is the gap this project can fill.
- **Hollywood Phase 2 timing**: Lyman Pl to Fountain Av along Sunset Bl, centred on the six-way junction of
  Hollywood, Sunset, Sunset Dr, Virgil and Hillhurst. Draft design, survey open September 2026,
  implementation anticipated early 2027.
- **Vermont Transit Corridor BRT (Metro)**: 12.4 miles, 26 stations, dedicated bus lanes. Groundbreaking
  reported 21 October 2026. $149.9M federal grant September 2026; reported fully funded with state funds and
  Measure M. Target opening most often cited as 2028; no confirmed opening date found. Consequence: the
  existing Vermont archive (2016 to October 2026) is the pre-construction baseline for lines 204 and 754, and
  speeds from now on include construction effects.
- **Sunset East Phase 1**: Sunset Bl / Cesar Chavez Av, Douglas St to Alameda St (line 4). In design. Proposal:
  one car lane each way, dedicated bus and bike lanes, most street parking removed. LADOT estimates bus
  speeds up 15% and car trips 1 to 3 minutes longer. LADOT cites 126 fatal or serious-injury crashes,
  14 deaths, 2014 to 2025 on the Sunset / Cesar Chavez section. About $10M reported secured (older article).
- **Sunset East Phase 2**: Fountain Av to Douglas St. Outreach launched September 2026.
- No construction date was found for either Sunset East phase, so that corridor is a **baseline**: every
  month of measured data collected before construction is the "before".
- The project page `ladotlivablestreets.org/projects/sunset` is rendered by JavaScript and could not be read
  by an automated fetch; open it in a browser for the official timeline.
- Dated events with source links are stored in `corridors/sunset.json` under `events`.
- Fountain Av road diet: not yet researched.

Scheduled speeds for lines 2, 4 and the former 704 on the Sunset corridor since 2018 are in
`data/corridors/sunset/` (built by `pipeline/backfill_corridor.py`).

## 0. Done already: start archiving lines 2 and 4

GPS history cannot be recovered later, so the live Cloudflare collector now records lines 2 and 4 as
well as 204 and 754 (`ROUTES` in `wrangler.jsonc`). Raw pings land in R2. Nothing downstream uses them yet.

## 1. Why the Vermont method is not enough

- The 10-year series is **scheduled** speed. Timetables lag and often stay flat for a year or more, so they
  cannot show a before/after effect at a project date. Before/after needs **measured** data.
- Fountain Av has **no bus**, so no GTFS source at all.
- Hollywood and Sunset run east-west and diagonally. `pipeline/corridor.py` assumes a north-south street
  and uses latitude as position. That has to become real linear referencing along a line.

## 2. Data sources by question

| Question | Source | Covers before? | Access |
|---|---|---|---|
| Bus speed and reliability | Cal-ITP GTFS-RT archive (about 2022 on) | Yes, if the project is 2022 or later | By request (see `AGENTS.md`) |
| Bus speed going forward | Our Cloudflare collector | No, starts 2026-11-17 | Running |
| Bus speed, long context | LA Metro GTFS history (scheduled) | Yes, weak signal | Open |
| Bus speed, official | Swiftly API | Maybe, ask about history | Key requested |
| Collisions and injuries | LAPD traffic collision data on data.lacity.org; SWITRS via UC Berkeley TIMS | Yes, many years | Open |
| Car volumes | LADOT traffic counts (data.lacity.org) | Sparse, by count date | Open |
| Car speeds | LADOT speed surveys; INRIX / RITIS / StreetLight / Replica | Yes for vendors | Vendor data needs an agreement |
| Bike and scooter trips | LADOT's MDS data (trips, telemetry) | Yes, since about 2019 | Request to LADOT |
| Bike counts | Strava Metro; LADOT counters | Yes | Free for agencies / request |
| Project dates and extents | LADOT project pages, council files, StreetsLA | n/a | Open, must be cited |

**The OMF story gets stronger here.** MDS is built for shared bikes and scooters, and LADOT created it.
Trip counts and speeds on Fountain and Hollywood before and after the redesign are a native MDS use,
unlike bus speeds. This is the best fit for a CoMotion audience and the only vehicle-level source for
Fountain. It depends on LADOT sharing aggregated MDS data.

**Collisions are the fastest win.** Open, years deep, geocoded, and the metric a road diet is meant to move.
It works for every corridor, including Fountain, with no access requests.

## 3. Method

1. **Corridor registry.** Replace `corridor.py` with a `corridors/` folder: one small file per corridor
   holding a line geometry (from GTFS shapes or OpenStreetMap), named section breaks, the bus routes on it,
   and a list of **events** (`date`, `label`, `section`, `source_url`).
2. **Linear referencing.** Project stops and GPS pings onto the corridor line to get distance along it.
   Keep the Vermont result identical as the regression test.
3. **Treated versus control.** For each project pick a control: the adjacent untreated stretch of the same
   street (Hollywood past the Vista Theatre for line 2) or a parallel street. Report the change on the
   treated section minus the change on the control (difference in differences).
4. **Like with like.** Compare the same months a year apart, same day type, same hours. Exclude the
   construction period. Show the middle value and the 20th to 80th percentile range, not just an average.
5. **Metrics per corridor.**
   - Bus: speed, end-to-end minutes, spread between slow and fast trips (reliability).
   - Safety: collisions per year, and those with serious injury or death; by mode where recorded.
   - Activity: car counts where available; bike and scooter trips from MDS.
6. **State the limits on the page.** Short "after" windows, citywide trends, and for collisions small
   numbers that swing year to year.

## 4. Schema changes

- Add `corridor_id` to the hourly table; sections become `corridor_id` + `section_id`.
- New tables: `events` (project milestones), `collisions` (one row per collision snapped to a section),
  `counts` (dated volume or trip counts with `mode` and `source`).
- Keep one Frictionless `datapackage.json`; one Parquet folder per corridor.
- Store measured and scheduled rows in the same shape, distinguished by `source`, as now.

## 5. Page changes

- Corridor picker at the top; the street strip becomes that corridor's sections, with the treated
  stretch marked.
- A vertical marker at each event date on the time series.
- A before/after panel: paired bars or dot-and-range for treated and control, with the difference stated
  in words.
- A collisions-per-year chart with the event marked.

## 6. Order of work

1. **Verify facts** for each corridor: exact extents, what was installed, opening dates, which bus lines
   run where today (read from the current GTFS, do not assume). About half a day.
2. **Collisions before/after** for all four corridors from open data. Fastest visible result.
3. **Corridor registry and linear referencing**, with Vermont as the regression test.
4. **Scheduled series for lines 2 and 4** (reuse the backfill) as long-run context.
5. **Send the access requests now**, since they take weeks: Cal-ITP archive for lines 2 and 4, LADOT
   for aggregated MDS trips on Fountain and Hollywood, Swiftly history.
6. **Measured before/after** for the bus corridors once Cal-ITP or Swiftly history arrives; until then
   show measured data from our own collector as "after only".
7. **Fountain Av activity** from MDS and counts when LADOT responds.
8. **Page rebuild** with the corridor picker and before/after panel.

## 7. Open questions for the owner

- Which exact blocks and dates for each project? Is Sunset east / Cesar Chavez already redesigned, or a
  baseline for a planned project?
- Is there a contact at LADOT for MDS aggregates and speed surveys?
- Is a vendor source (INRIX, StreetLight, Replica) available through a partner agency?
- Rename the project and resources from "vermont" to something corridor-neutral before adding more?
