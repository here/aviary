# Collisions, traffic incidents and emergency response: what exists

Checked from the cloud session on 2026-11-18 by querying each source directly. Queued as roadmap items E1 to E4.

## Summary

| Item | Best source found | Reachable now? | History | Location detail | Fit |
|---|---|---|---|---|---|
| Collisions | **California Crash Reporting System (CCRS)** on data.ca.gov (CHP) | Yes, open API, no key | 2016 to two days ago | Latitude/longitude, primary and cross street | Strong |
| Collisions (older city file) | LAPD "Traffic Collision Data from 2010 to Present" (`d5tf-ez2w`, data.lacity.org) | Yes | 2010 to **2025-03-08** (stopped updating) | Address, cross street, point | Backup for 2010 to 2015 |
| Traffic incidents | **TomTom Incident Details API v5** | Yes, with the existing TomTom key | **Present only**: no history, so collect from now on | From/to street names and a line | Good, for flagging unusual hours |
| Emergency response times | **LAFD Station Response Metrics** (`4hqz-rxff`) | Yes | Monthly, 2016 to September 2026 | Per fire station area | Medium: monthly and by station area, not by street |
| Emergency response, raw | LAFD Response Metrics raw data (`n44u-wxe4`) | Yes | 8.6 million unit dispatches from 2016; last updated 2026-02 | Fire district only; time of day but **no date column** | Weak |
| Police calls | LAPD Calls for Service 2024 to present (`xjgu-z4ju`) | Yes | 2024 onward, daily updates | Reporting district | Weak: dispatch time only, no arrival time |

## 1. Collisions

**CCRS** (`data.ca.gov/dataset/ccrs`) publishes three tables per year from 2016 to 2026: Crashes, Parties, and
Injured/Witnesses/Passengers. The 2026 Crashes table had 324,418 records on 2026-11-18, updated that day, and
includes LAPD reports (NCIC code `1942`, 11,038 crashes in the City of Los Angeles up to 2026-11-16).
- **Useful fields**: date and time, latitude/longitude, primary and secondary road, collision type, number injured
  and killed, hit and run, primary collision factor, pedestrian action. Environmental fields: **weather, road
  surface, road condition and lighting**.
- **Query**: CKAN `datastore_search_sql` on `data.ca.gov`, which is already on the session allowlist.
- **To check before use**:
  - LAPD counts per year: 38,382 in 2016 against 12,851 in 2024. That drop is too large to be real, so first check
    whether the reporting scope or the move to CCRS changed what is included.
  - Preliminary reports are flagged with `Is Preliminary`.
- **Alternatives**:
  - SWITRS through UC Berkeley TIMS: geocoded, but needs a free login and lags behind.
  - The LAPD city file above, for years before 2016.

## 2. Traffic incidents

**TomTom Incident Details v5** works with the key the traffic Worker already uses. A query over central LA returned
46 current incidents.
- **What each incident gives**: category (accident, jam, roadworks, closure and others), delay magnitude, start time,
  from and to street names, and the length of the delay.
- **Limitation**: it lists only what is happening now, so a history means polling it. Every 15 minutes, beside the
  flow tiles, would be one request per run: 96 a day, or 2,880 a month. That is over Incident Details' free allowance of
  2,500 a month, so poll every 20 minutes or use the incident vector tiles, which share the flow tiles' 200,000 a month
  ([`docs/FREE_TIERS.md`](../FREE_TIERS.md)).
- **Fit with existing data**: the flow tiles we already store carry a `road_closure` flag per road piece, and
  `build_traffic.py` reports it as `closed_share`. Incidents would add the *reason* and the *start time*.
- **Other sources**:
  - Waze for Cities alerts and jams, through LADOT (roadmap A3).
  - BOE/LADOT street-work permits (roadmap C5).

## 3. Emergency response

**LAFD Station Response Metrics** gives, per station and month: average EMS and non-EMS turnout and travel time, call
counts, and averages for structure fires and critical ALS (advanced life support) calls. It runs from 2016 to
September 2026. A citywide version (`kcsj-s69p`) can serve as the control.
- **What it answers**: the common objection that road diets slow fire engines and ambulances. Compare travel times
  at the stations whose first-in areas the corridor crosses, before and after, against citywide or distant stations.
- **Limits**:
  - Monthly averages by station area mix many streets.
  - A station's area is far bigger than one corridor.
  - Effects will be small and noisy, so treat results as a check, not proof.
- **Coverage gaps**:
  - **Fountain Av / West Hollywood** is served by LA County Fire and the Sheriff, which publish nothing comparable.
    It would need a records request.
  - Ambulance GPS traces and signal pre-emption logs (LADOT) are not public. They would need a request.
- **Police**: calls for service give demand by reporting district but not travel or arrival time. They are not
  useful for travel time.

## How these help confirm traffic-flow trends under different conditions

1. **Explain outlier hours.** Incidents and closures on a section explain slow hours that are not part of the trend.
   Flag them in the hourly roll-ups (`incident_share` beside `closed_share`). Trends can then be shown with and
   without disrupted hours, and the cost of incidents measured on its own.
2. **Conditions as a stratifier.** CCRS records the weather, road surface and lighting for each crash. Speeds need
   the same conditions **per hour**, which CCRS cannot give for crash-free hours. Add hourly weather from NOAA (ASOS
   stations at downtown USC and LAX) and compute sunset times. Then compare bus and traffic speeds on wet against
   dry days, and dark against light, before and after each project.
3. **Safety outcome against speed.** Crashes, especially injury and pedestrian crashes, per section per year before
   and after each redesign, set beside the bus and traffic speed change. This answers "safer, at what cost to travel
   time?". Counts per street are small, so use multi-year windows and a comparison street.
4. **Emergency travel time as a second speed measure.** LAFD station travel times are an independent check on
   general-traffic speed trends near each corridor, at monthly resolution back to 2016. That is longer than the
   TomTom series, which starts 2026-11-18.

## Suggested order

1. **E1: CCRS collisions.** Download, snap to sections, and write yearly and monthly per-section counts by severity
   and conditions. It is open, has history to 2016 and is current.
2. **E2: TomTom incidents.** Add to the traffic Worker now, because each day not collected is lost. Roll up into an
   hourly flag.
3. **E3: hourly weather (NOAA).** Needed for any environmental comparison. Check the host allowlist.
4. **E4: LAFD station metrics.** Map the stations covering each corridor, then a monthly before/after with a citywide
   control.
