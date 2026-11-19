# Traffic incidents on each stretch: what to record

**Top-level requirement (owner, 2026-11-19)**: for every street and section, keep a record of traffic incidents
over time, and keep it going, next to the bus and traffic speeds.

This note decides *what* to record before anything is built. Sources were checked from the session on 2026-11-18
and 2026-11-19; build steps are roadmap items E1, E2 and E5.

## The data points

| Data point | Meaning here | Source | History | How often it updates |
|---|---|---|---|---|
| **Delay (recurring)** | Minutes lost per section and hour against free flow: travel time minus free-flow travel time | Our TomTom and HERE flow data (`travel_time_min`, `free_flow_mph`): a derived column, nothing new to collect | From 2026-11-18 | Hourly (already collected) |
| **Delay (bus)** | Measured bus minutes against the timetable for the same section and hour | Our bus GPS and timetable series | From 2026-11-18 | Hourly (already collected) |
| **Incident delay** | A live incident on the stretch, with TomTom's delay in seconds and size from 0 (unknown) to 4 (road closed) | TomTom Incident Details | From the day collection starts; none before | Every 20 minutes |
| **Incident type** | Accident, jam, roadworks, lane closed, road closed, broken-down vehicle, flooding, and others (TomTom's icon categories) | TomTom Incident Details | Same | Same |
| **Collision, by severity** | One record per reported crash, graded on the standard injury scale (KABCO) | CCRS (state crash database on data.ca.gov, includes LAPD) | 2016 to two days ago | Daily, with late reports and revisions |
| **Traveller type** | Who was involved and who was hurt: pedestrian, bicyclist, motorcyclist, e-scooter or other small vehicle, car occupant, bus, parked vehicle, autonomous vehicle | CCRS Parties (`PartyType`, vehicle type) and Injured (`InjuredPersonType`) tables | 2016 on | Same |
| **Age band** | Child 0 to 14, youth 15 to 17, adult 18 to 64, older adult 65 and up, unknown | CCRS `StatedAge` (Parties and Injured) | 2016 on | Same |
| **Conditions** | Weather, lighting (daylight, dark with or without street lights), road surface, hit and run, primary cause (for example unsafe speed, failure to yield to a pedestrian) | CCRS Crashes | 2016 on | Same |

### Severity scale (from CCRS `ExtentOfInjuryCode`)

| Level | CCRS code | Plain words | In the owner's list |
|---|---|---|---|
| K | `Fatal` | Someone died (within 30 days) | fatality |
| A | `SuspectSerious` (and older `SevereInactive`) | Serious injury: broken bones, hospital admission | major |
| B | `SuspectMinor` (and older `OtherVisibleInactive`) | Minor visible injury | minor |
| C | `PossibleInjury` (and older `ComplaintOfPainInactive`) | Possible injury, complaint of pain | minor |
| O | no injured person recorded | Property damage only | minor (no injury) |

A collision takes the severity of its worst-hurt person. **KSI** (killed or seriously injured, K + A) is the usual
safety measure for street redesigns. LADOT's Pico figures ("75 crashes with severe injury or death, 2014 to 2023")
are KSI.

### Traveller types (CCRS values mapped to a short list)

- **Pedestrian**: `PartyType = Pedestrian`, or `InjuredPersonType = Pedestrian`.
- **Bicyclist**: `PartyType = Bicyclist`.
- **Motorcyclist, scooter or other small vehicle**: from the vehicle type of a `Driver` party.
- **Car or truck occupant**: a `Driver` party, or `Passenger` among the injured.
- **Bus**: from the vehicle type. This matters on bus streets, and later for bus lanes.
- **Parked vehicle**: `PartyType = ParkedVehicle`.
- **Autonomous vehicle**: `PartyType = AutonomousVehicle`, a separate class. There are 390 parties statewide so far
  in 2026, which is useful for the robotaxi part of the talk.

## What gets stored

1. **`collisions`**: one row per collision on a study street, matched to its section, from CCRS.
   - Collision id, local date and time, section and direction where known, and the nearest cross street.
   - Severity (K, A, B, C or O), and counts killed, seriously injured, minor and possible.
   - Flags: pedestrian, bicyclist, motorcyclist or small vehicle, child, older adult, and autonomous vehicle
     involved; hit and run.
   - Primary cause, weather, lighting, surface, and a preliminary flag.
   - No names exist in the source. Leave out gender and race; publish age as a band only.
2. **`incidents`**: one row per live TomTom incident per section, from Incident Details.
   - Incident id, first seen and last seen (the incident is tracked across polls by its id), type and size.
   - Largest reported delay, from and to street names, and direction.
3. **Section-month summary**: collisions by severity and traveller type, KSI per mile, incident hours by type, and
   delay minutes. This is what the page charts.
4. **Hourly delay columns**: added to the existing traffic CSVs: `delay_min`, which is `travel_time_min` minus the
   free-flow travel time.

### Matching rules

- A collision belongs to a stretch when its point lies within about 30 m of the street's path. Crashes in the
  intersections at both ends count, because that is where most pedestrian injuries happen.
- Check CCRS `PrimaryRoad` and `SecondaryRoad` against the street name, so that a crash on a parallel street
  nearby is not counted.
- An incident belongs to a section when its line runs along the path, using the same rule as the traffic pieces
  (within 40 m, mostly along the path).

## Sources, access and cost

| Source | Access | Cost and limits |
|---|---|---|
| CCRS (Crashes, Parties, Injured, 2016 to 2026) | `data.ca.gov` CKAN SQL API, no key; already on the session allowlist | Free. Check first why LAPD's yearly count drops from 38,382 (2016) to 12,851 (2024): reporting scope may have changed |
| LAPD collision file, 2010 to March 2025 (`d5tf-ez2w`, data.lacity.org) | Socrata, no key | Free. For years before 2016 only; it has no injury detail |
| TomTom Incident Details | Existing key | Free: 2,500 requests a month. **One bounding box over all streets every 20 minutes is about 2,160 a month** (check the box size limit). Polling every 15 minutes would go over |
| HERE incidents (v7) | Existing key | Shares HERE's 5,000-a-month allowance with flow (about 3,400 already used), so not affordable on top |
| SWITRS / UC Berkeley TIMS | Free login | Geocoded and cleaned, but runs months behind; useful to cross-check CCRS |

## Gaps and cautions

- **Small numbers.** One street sees a few KSI crashes a year. Compare multi-year windows before and after, and
  use the control streets (C12), not month-to-month changes.
- **Reporting.** Property-damage-only crashes are badly under-reported, and pedestrian and bicyclist injuries are
  under-reported too. Say so on the page.
- **CCRS revisions.** Preliminary records change, so re-fetch the last 90 days on every run.
- **Live incidents have no history.** They exist only from the day polling starts. Start E2 soon.
- **Emergency response** (roadmap E4) and **weather** (E3) sit next to this requirement but are separate sources.
