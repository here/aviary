# Offline trip and stop matching for schedule adherence

November 2026 [delay audit](../audits/2026-11-26-transportation-evidence.md#three-delay-measures). Related roadmap item [B3](../ROADMAP.md#b-bus-speed-work).

Run from the repository root with Python 3.10+ and installed IANA timezone data.

```sh
python3 docs/validation/trip_stop_matching.py -v
```

The 12 tests passed locally. The script embeds all event and schedule fixtures and makes no network
calls. Its synthetic trips isolate matching cases that depend on overnight overlaps and daylight
saving transitions. The archive's checked-in [feed version index](../../data/feed_versions.csv)
ended on 2026-11-15 at the audit pin. It records historical backfill ranges and contains no stop
times or event-to-feed mapping. The overnight examples below use invented trips and snapshots.

## Findings

| Case | Fixture result |
|---|---|
| Calendar | Weekly service requires an in-range date and active weekday. An explicit removal suppresses it and an explicit addition can activate it outside the base range. An exceptions-only feed can use an empty base weekday set. |
| LA service day and static version | Thursday's `24:05:00` and Friday's `00:05:00` both mean Friday 08:05 UTC in the fixture, and the same trip ID appears in each version. The supplied service date selects the version and trip instance. A missing service date or unresolved version leaves no match. |
| Daylight saving | Convert LA local noon on the service date to UTC, subtract 12 elapsed hours, then add the GTFS time as elapsed seconds. Tests assert UTC independently across standard time, daylight time and both transitions, including the two distinct occurrences of fall-back 01:30. |
| Stop occurrence | Use `stop_sequence` as an identifier, with no assumption of contiguous numbering. When both sequence and ID exist, require agreement. Accept a stop-ID-only record only if it identifies one visit within the trip. Repeated stop IDs, duplicate sequence rows and mismatching IDs are tested. |
| Signed deviation | Compute actual UTC minus the exact scheduled UTC time for the same arrival or departure. One 00:06 LA event is 60 seconds late for a 00:05 arrival and 60 seconds early for a 00:07 departure. An exact match returns zero. |
| Repeats and conflicts | Group by feed namespace, static version, service date, trip ID, resolved stop sequence and event kind. Replays of the same instant coalesce even when UTC offsets or receipt times differ. Conflicting observed instants for a key quarantine that key regardless of order. |
| Evidence | Past predictions and inherited delays remain excluded, as does unknown evidence. A later receipt timestamp does not establish observation. A confirmed actual can match even when a prediction for the same key also appears. |
| Out of scope for the fixture | Frequency-based trips, cancellations and skipped stops, approximate or missing schedule times, and records with missing absolute timestamps do not produce deviations. Added, replacement and duplicated service would need their own instance rules. |

The fixture is a reference test for normalized inputs. A real pilot needs a parser for the licensed event
source and its paired static GTFS files, including `agency.txt`, `trips.txt`, `stop_times.txt` and the
calendar files. Pin the GTFS revision or checksum and its applicability to the service date, including
cutovers and any feed supersessions. Preserve separate arrival and departure counts, audit unmatched
rows and conflicts, and measure coverage by route, direction, stop and service period against eligible
scheduled stop events. Report missing observations separately from measured zero deviations.
[GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/)

## Required actual event record

| Field | Requirement |
|---|---|
| Source and schedule identity | Provider and agency/feed namespace, source schema version, and feed revision or a documented mapping to exactly one applicable static snapshot. |
| Trip instance | Static `trip_id` and agency-local service date, such as a provider's verified `start_date`. Preserve trip relationship and any provider instance or scheduled start identifier used to distinguish runs. Route and direction can corroborate identity if supplied. |
| Stop occurrence | `stop_sequence` preferred. Preserve `stop_id` if supplied and verify it against the selected static row. Stop-only fallback needs a single visit in that trip. Include stop relationship and any reassignment flag. |
| Event kind and occurrence time | Arrival or departure, with the actual occurrence as a UTC epoch or an offset-aware timestamp. Record event precision. Compare arrival with scheduled arrival and departure with scheduled departure. |
| Observation evidence and audit | A provider-confirmed actual-event marker or a documented direct observation method, distinct from predictions and inferred passage. Keep provider record/event ID if available, receipt or export timestamp, and correction or supersession metadata if the provider supplies it. These fields support replay and correction review. |

Generic GTFS Realtime trip updates can contain predictions, updates for past stops and delay values
propagated across stops. An absolute timestamp, zero uncertainty, a past stop time, a delay alone, or
a feed or trip update timestamp cannot by itself establish a measured stop arrival or departure. The
fixture admits only the `observed` provenance class. Confirm what a provider's marker means before
mapping it to that class. The repository describes 15-minute trip-update snapshots. Even with a
documented actual marker, coverage depends on how long those values remain visible and whether an
event export is available.
[GTFS Realtime reference](https://gtfs.org/documentation/realtime/reference/) ·
[GTFS Realtime Trip Updates](https://gtfs.org/documentation/realtime/feed-entities/trip-updates/)

## Remaining gates

- Confirm with Swiftly or LA Metro which product or export provides verified actual arrivals and
  departures, coverage and history, trip and snapshot identifiers, timestamp precision, and correction
  rules. Collection access and measurement availability are separate questions.
- Confirm the owner's authorization and applicable provider terms before accessing actual event
  records for this work. Verify permitted collection and historical retrieval, local and R2 storage
  and retention, team access, and permitted joins with static GTFS. Confirm any obligations to delete
  or restrict identifiers and whether existing credentials cover the source.
- Obtain permission for any intended redistribution separately, including raw or per-stop events,
  derived deviation aggregates, and scheduled extracts if distributed. Record allowed granularity and
  attribution for each planned output. The synthetic results establish matching behavior only.
