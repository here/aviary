# Pico Boulevard Safety and Mobility Project (LADOT)

Project page: https://ladotlivablestreets.org/projects/pico. The page is rendered by JavaScript, so the session
could not read it; the facts below come from news reports and should be checked against it before quoting.

## What and where

- **Extent**: about 3.5 miles of Pico Bl, **Crenshaw Bl to Figueroa St** (LAist, 2026-07-10; Spectrum News,
  2026-07-29; an earlier LAist item, 2026-03-09, says 3.4 miles).
- **Changes**:
  - Two travel lanes each way become one, plus a center turn lane (also for emergency vehicles).
  - Curb- or barrier-protected bike lanes.
  - New signals (TOUCAN crossings) at Manhattan Pl and New Hampshire Av, and shorter crossing distances.
  - Sidewalk and curb-ramp repairs.
  - Parking removed, mostly on the north side. Reports differ: about 270 of roughly 480 spaces (March), or 228
    spaces (July).
  - Later adjustments: loading zones, more south-side and side-street parking, **relocating some bus stops**, more
    ADA parking, and no more peak-hour parking restrictions.
- **Expected effect on travel time** (LADOT, via LAist): peak-hour travel could rise by roughly one to two minutes per
  mile. That is exactly what this project's bus and traffic series can measure.
- **Safety case**: 75 crashes with severe injury or death from 2014 to 2023. Nearly three-quarters involved people
  walking or biking, and all 11 people killed were pedestrians.

## Dates

| When | What | Source |
|---|---|---|
| May 2025 | Outreach begins (survey of more than 1,100 people; 74 to 75% favoured protected bike lanes) | LAist 2026-07-10 |
| Late 2026 | Construction expected to begin, in phases over about a year | LAist 2026-07-10, Spectrum 2026-07-29 |
| Spring 2027 | Opening reported, ahead of the 2028 Olympics (Crypto.com Arena, near the east end, is a venue) | LAist 2026-03-09 |

The project is one of the redesigns advancing under Measure HLA.

## How it is tracked here

- **Street definition**: `corridors/pico.json`, Crenshaw Bl to Bonnie Brae St (2.65 mi), in three sections:
  Crenshaw Bl to Western Av, Western Av to Vermont Av, and Vermont Av to Bonnie Brae St. All three are inside the
  project.
- **Bus**: **Metro line 30** is the only Metro line on this stretch. It leaves Pico at Bonnie Brae St (via Union Av
  and Olympic Bl) and rejoins at Figueroa St, so **Bonnie Brae St to Figueroa St (about 0.6 mi) has no bus data**.
  The corridor stops there rather than mixing detour time into a Pico section. Line 30 starts at Pico / Rimpau, just
  west of Crenshaw, so there is no untreated control section on Pico itself.
  - Scheduled speeds since 2018 come from the GTFS history (`data/corridors/pico/hourly/`).
  - Measured speeds come from Swiftly vehicle positions (Metro's websocket collector does not subscribe to line 30).
  - Measured history: Cal-ITP speed maps for 12 Wednesdays from November 2024 (`data/corridors/pico/calitp/`).
- **General traffic**: TomTom flow tiles, 3 extra zoom-14 tiles from 2026-11-19. The first snapshot covered 93% of
  the street in both directions. Pico from Bonnie Brae St to Figueroa St is not rolled up yet; adding it means a
  traffic-only section that the bus roll-ups skip (roadmap C8).
- **Before window**: with construction starting late 2026, measured bus GPS (from 2026-11-18) and TomTom give only
  weeks of "before". The Cal-ITP snapshots (2024-11 to 2026-07) and the timetable history carry the longer before
  period.

## Control street: Olympic Bl

`corridors/olympic.json` covers Olympic Bl from Crenshaw Bl to Figueroa St, parallel to Pico and about 0.4 mi north.
It uses the same cross streets as section boundaries:

| Section | Pico Bl (treated) | Olympic Bl (control) |
|---|---|---|
| S1 | Crenshaw Bl to Western Av, 0.99 mi | Crenshaw Bl to Western Av, 0.81 mi (Crenshaw slants east going north) |
| S2 | Western Av to Vermont Av, 0.99 mi | Western Av to Vermont Av, 1.00 mi |
| S3 | Vermont Av to Bonnie Brae St, 0.66 mi | Vermont Av to Bonnie Brae St, 0.76 mi |
| S4 | not tracked (no bus on Pico) | Bonnie Brae St to Figueroa St, 0.94 mi |

- **Bus**: Metro line 28 runs the whole stretch. Line 30 also uses Olympic from Union Av to Georgia St on its
  detour, but is left out, so Pico's timetable changes do not leak into the control.
- **Data**: scheduled speeds since 2018, Cal-ITP history (13 dates), measured speeds from Swiftly, and TomTom
  traffic. Olympic adds one TomTom tile, for 26 in all.
- **Method**: compare the change on Pico with the change on Olympic over the same hours and dates
  (difference in differences). The figure is Pico's after-minus-before, less Olympic's after-minus-before, per
  section and time of day.
- **Caveat**: drivers avoiding Pico during or after construction may slow Olympic. That would make Pico look
  better than it is against the control. If Olympic slows once construction starts, add a more distant control,
  such as Venice Bl or Washington Bl.

## Open questions

- Exact construction start and phase order (check the LADOT page and weekly updates).
- Which bus stops move, and when: stop moves change line 30's timetable and dwell times.
- Whether LADOT DASH or Big Blue Bus (Rapid 7 ends at Pico / Rimpau) use any of the stretch. Neither is in Metro's
  feed.
