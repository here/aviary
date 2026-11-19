# Westwood Boulevard Safety and Mobility Project (LADOT)

Project page: https://ladotlivablestreets.org/projects/westwood. The page text below was supplied by the owner on
2026-11-19, because the page is rendered by JavaScript and the session cannot read it.

## What LADOT proposes

- **Phase**: planning and design. Council District 5; North Westwood, Westwood and Westside Neighborhood Councils.
- **Changes**:
  - Class IV protected bike lanes, 2.2 mi.
  - Bus-only lanes, 1.1 mi, with new boarding platforms. LADOT says buses would be **14 to 20% faster**.
  - Pedestrian safety improvements.
- **Purpose**: connect UCLA and Westwood Village with the Metro E Line (Westwood/Rancho Park station) and the future
  D Line station at Wilshire Bl. Required under Measure HLA (Healthy Streets LA): the street is on the Mobility Plan
  2035 Bicycle Enhanced, Bicycle Lane and Transit Enhanced Networks and a Pedestrian Enhanced District.
- **Car travel**: up to **1 minute 50 seconds more per mile** at the busiest times (LADOT estimate).
- **Parking**: 75 to 80% of on-street spaces kept. Between Santa Monica Bl and Pico Bl, 73 part-time (peak-hour
  restricted) spaces become 63 all-day spaces.
- **Safety**: the design elements are cited as reducing injury crashes by 36%.

## Timeline (LADOT)

| When | What |
|---|---|
| Fall 2025 | Engagement phase 1: more than 5,000 people through pop-ups, surveys and events |
| Fall 2026 | Engagement phase 2, with paid Community Ambassadors (applications closed October 9) |
| Winter 2026 | Finalize design |
| Spring 2027 | Construction phase 1 (curb ramps) |

## How it is tracked here

- **Street definition**: `corridors/westwood.json`, Le Conte Av to the E Line crossing at Westwood/Rancho Park station,
  2.1 mi, close to the 2.2 mi of bike lanes. LADOT's page gives no exact extents and does not say which 1.1 mi gets
  bus lanes; confirm both when the design is published. Directions are northbound and southbound, and the strip runs
  North to South.

| Section | Stretch | Length | Bus data | Traffic |
|---|---|---|---|---|
| S1 | Le Conte Av to Wilshire Bl (Westwood Village) | 0.38 mi | Metro 761, 233 | Southbound only in the first snapshot |
| S2 | Wilshire Bl to Santa Monica Bl | 0.67 mi | Metro 761, 233 | Both directions |
| S3 | Santa Monica Bl to Pico Bl | 0.55 mi | None (Big Blue Bus only) | Both directions |
| S4 | Pico Bl to the E Line | 0.53 mi | None (Big Blue Bus only) | Both directions |

- **Bus**: Metro 761 and 233 stop on Westwood Bl from Le Conte Av to Santa Monica Bl, after which 761 heads for
  Sepulveda Bl. That gives scheduled speeds (Metro's timetables place these lines' stops on this stretch from June 2021 on), Cal-ITP measured history (13 dates) and Swiftly GPS for S1
  and S2.
  - South of Santa Monica Bl the buses are Santa Monica's Big Blue Bus. Our Swiftly key returns 403 for other
    agencies, and Big Blue Bus's own GTFS host is not on the session allowlist.
  - Adding Big Blue Bus would need its GTFS and GTFS-realtime feeds, which are public, and the host on the allowlist.
    That is roadmap item C11.
- **Traffic**: TomTom Vector Flow Tiles, 4 extra zoom-14 tiles (30 in all) from 2026-11-19.
- **Bus-lane effect to check**: LADOT's "14 to 20% faster" claim can be tested directly once the bus lanes are built,
  if they fall on S1 or S2.

## Open questions

- Exact extents of the bike lanes and of the 1.1 mi of bus lanes.
- Whether the bus lanes are peak-only or all-day.
- A control street. Candidates are Sepulveda Bl (line 761 south of Pico, and line 234) or Overland Av, with no Metro
  service.
