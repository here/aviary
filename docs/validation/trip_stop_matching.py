"""Offline validation of scheduled stop matching with synthetic data only."""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import unittest
from zoneinfo import ZoneInfo


LA = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc
THURSDAY = date(2026, 11, 26)
FRIDAY = date(2026, 11, 27)


@dataclass(frozen=True)
class Calendar:
    first: date
    last: date
    weekdays: frozenset[int]  # Monday is 0.
    exceptions: dict[date, int]  # GTFS 1 adds service, 2 removes service.

    def active(self, day):
        if day in self.exceptions:
            return self.exceptions[day] == 1
        return self.first <= day <= self.last and day.weekday() in self.weekdays


@dataclass(frozen=True)
class Stop:
    sequence: int
    stop_id: str
    arrival: str | None
    departure: str | None
    exact: bool = True


@dataclass(frozen=True)
class Trip:
    trip_id: str
    service_id: str
    stops: tuple[Stop, ...]
    fixed_schedule: bool = True


@dataclass(frozen=True)
class Schedule:
    namespace: str
    version: str
    valid_from: date
    valid_through: date
    calendars: dict[str, Calendar]
    trips: tuple[Trip, ...]


@dataclass(frozen=True)
class Event:
    namespace: str
    trip_id: str
    service_date: date | None
    sequence: int | None
    stop_id: str | None
    kind: str
    evidence: str
    occurred_at: datetime | None
    recorded_at: datetime
    trip_relationship: str = "scheduled"
    stop_relationship: str = "scheduled"
    feed_version: str | None = None


def schedule_utc(service_date, gtfs_time):
    hour, minute, second = map(int, gtfs_time.split(":"))
    if hour < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError("Invalid GTFS time")
    noon = datetime.combine(service_date, time(12), LA).astimezone(UTC)
    return noon - timedelta(hours=12) + timedelta(hours=hour, minutes=minute, seconds=second)


def match(event, schedules):
    """Return (reason, key, actual UTC, scheduled UTC). Only matches have a key."""
    reason = check_event(event)
    if reason:
        return reason, None, None, None

    day = event.service_date
    versions = [
        schedule for schedule in schedules
        if schedule.namespace == event.namespace
        and schedule.valid_from <= day <= schedule.valid_through
        and (event.feed_version is None or schedule.version == event.feed_version)
    ]
    if len(versions) != 1:
        return ("schedule_missing" if not versions else "schedule_ambiguous"), None, None, None

    schedule = versions[0]
    trips = [trip for trip in schedule.trips if trip.trip_id == event.trip_id]
    if len(trips) != 1:
        return ("trip_missing" if not trips else "trip_ambiguous"), None, None, None
    trip = trips[0]
    if not trip.fixed_schedule:
        return "unsupported_trip", None, None, None
    calendar = schedule.calendars.get(trip.service_id)
    if calendar is None or not calendar.active(day):
        return "inactive_service", None, None, None

    if event.sequence is not None:
        stops = [stop for stop in trip.stops if stop.sequence == event.sequence]
    else:
        stops = [stop for stop in trip.stops if stop.stop_id == event.stop_id]
    if len(stops) != 1:
        return ("stop_missing" if not stops else "stop_ambiguous"), None, None, None
    stop = stops[0]
    if event.stop_id is not None and stop.stop_id != event.stop_id:
        return "stop_conflict", None, None, None
    gtfs_time = getattr(stop, event.kind)
    if not gtfs_time or not stop.exact:
        return "no_exact_schedule_time", None, None, None

    key = (schedule.namespace, schedule.version, day.isoformat(), trip.trip_id, stop.sequence, event.kind)
    return "matched", key, event.occurred_at.astimezone(UTC), schedule_utc(day, gtfs_time)


def check_event(event):
    if event.evidence != "observed":
        return "unverified_event"
    if event.trip_relationship != "scheduled" or event.stop_relationship != "scheduled":
        return "unsupported_relationship"
    if event.kind not in ("arrival", "departure"):
        return "unsupported_event_kind"
    if event.service_date is None:
        return "missing_service_date"
    actual = event.occurred_at
    if actual is None or actual.utcoffset() is None or event.recorded_at.utcoffset() is None:
        return "missing_absolute_time"
    if actual.astimezone(UTC) > event.recorded_at.astimezone(UTC):
        return "future_occurrence"
    return None


def evaluate(events, schedules):
    """Aggregate only unambiguous actual events. Count each ignored input or group."""
    audit = Counter()
    observations = defaultdict(Counter)
    for event in events:
        reason, key, actual, scheduled = match(event, schedules)
        if reason == "matched":
            observations[key][(actual, scheduled)] += 1
        else:
            audit[reason] += 1

    deviations = {}
    for key, occurrences in observations.items():
        audit["duplicate_rows"] += sum(occurrences.values()) - len(occurrences)
        if len(occurrences) != 1:
            audit["conflicting_event_keys"] += 1
            continue
        actual, scheduled = next(iter(occurrences))
        deviations[key] = (actual - scheduled).total_seconds()
    return deviations, +audit


# The two feed versions deliberately reuse trip ids across the overnight cutover.
CALENDARS = {
    "regular": Calendar(THURSDAY, FRIDAY, frozenset({3, 4}), {}),
    "removed": Calendar(THURSDAY, FRIDAY, frozenset({3, 4}), {THURSDAY: 2}),
    "added": Calendar(FRIDAY, FRIDAY, frozenset(), {THURSDAY: 1}),
}
STOPS = (
    Stop(10, "loop", "23:58:00", "23:59:00"),
    Stop(30, "timepoint", "24:05:00", "24:07:00"),
    Stop(90, "loop", "25:10:00", "25:11:00"),
    Stop(100, "approximate", "25:12:00", "25:12:00", exact=False),
    Stop(110, "missing_time", None, None),
)
TRIP = Trip("night", "regular", STOPS)
NOV26 = Schedule("demo", "v1", THURSDAY, THURSDAY, CALENDARS, (
    TRIP, replace(TRIP, trip_id="exception_off", service_id="removed"),
    replace(TRIP, trip_id="exception_on", service_id="added"),
    replace(TRIP, trip_id="frequency", fixed_schedule=False),
))
NOV27 = Schedule("demo", "v2", FRIDAY, FRIDAY, CALENDARS, (
    replace(TRIP, stops=(Stop(30, "timepoint", "00:05:00", "00:07:00"),)),
))
SCHEDULES = (NOV26, NOV27)
EVENT = Event(
    "demo", "night", THURSDAY, 30, "timepoint", "arrival", "observed",
    datetime(2026, 11, 27, 8, 3, tzinfo=UTC),
    datetime(2026, 11, 27, 8, 15, tzinfo=UTC),
)


class OfflineFixtureTests(unittest.TestCase):
    def check_deviation(self, event, expected, schedules=SCHEDULES):
        deviations, audit = evaluate([event], schedules)
        self.assertEqual(list(deviations.values()), [expected])
        self.assertEqual(audit, {})
        return next(iter(deviations))

    def check_rejected(self, event, reason, schedules=SCHEDULES):
        self.assertEqual(evaluate([event], schedules), ({}, {reason: 1}))

    def test_weekday_range_is_inclusive(self):
        cal = CALENDARS["regular"]
        self.assertTrue(cal.active(THURSDAY))
        self.assertTrue(cal.active(FRIDAY))
        self.assertFalse(cal.active(THURSDAY - timedelta(days=7)))
        self.assertFalse(cal.active(FRIDAY + timedelta(days=7)))
        self.assertFalse(replace(cal, weekdays=frozenset({4})).active(THURSDAY))

    def test_service_exceptions_override_base_calendar(self):
        self.check_rejected(replace(EVENT, trip_id="exception_off"), "inactive_service")
        self.check_deviation(replace(EVENT, trip_id="exception_on"), -120)

    def test_service_day_survives_midnight_and_feed_cutover(self):
        self.assertEqual(EVENT.occurred_at.astimezone(LA).date(), FRIDAY)
        deviations, audit = evaluate([EVENT, replace(EVENT, service_date=FRIDAY)], SCHEDULES)
        self.assertEqual({key[1:3]: value for key, value in deviations.items()},
                         {("v1", "2026-11-26"): -120, ("v2", "2026-11-27"): -120})
        self.assertEqual(audit, {})
        self.check_rejected(replace(EVENT, service_date=None), "missing_service_date")
        self.check_rejected(replace(EVENT, feed_version="v2"), "schedule_missing")

    def test_la_utc_conversion_handles_standard_daylight_and_dst_transitions(self):
        cases = [
            (THURSDAY, "24:05:00", "2026-11-27T08:05:00+00:00"),
            (date(2026, 7, 1), "25:05:00", "2026-07-02T08:05:00+00:00"),
            (date(2026, 3, 8), "03:00:00", "2026-03-08T10:00:00+00:00"),
            (date(2026, 10, 31), "25:30:00", "2026-11-01T08:30:00+00:00"),
            (date(2026, 11, 1), "01:30:00", "2026-11-01T09:30:00+00:00"),
        ]
        for day, gtfs_time, expected in cases:
            with self.subTest(day=day, gtfs_time=gtfs_time):
                self.assertEqual(schedule_utc(day, gtfs_time).isoformat(), expected)

    def test_match_nonconsecutive_sequences_and_unique_stop_id_fallback(self):
        self.assertEqual(self.check_deviation(replace(EVENT, sequence=None), -120)[4], 30)
        loop = replace(EVENT, sequence=10, stop_id="loop",
                       occurred_at=datetime(2026, 11, 27, 7, 58, tzinfo=UTC))
        self.assertEqual(self.check_deviation(loop, 0)[4], 10)
        self.check_rejected(replace(loop, sequence=None), "stop_ambiguous")
        self.check_rejected(replace(EVENT, sequence=2), "stop_missing")
        self.check_rejected(replace(EVENT, stop_id="loop"), "stop_conflict")

    def test_signed_deviation_uses_matching_arrival_or_departure(self):
        actual = datetime(2026, 11, 27, 8, 6, tzinfo=UTC)
        events = [replace(EVENT, occurred_at=actual), replace(EVENT, kind="departure", occurred_at=actual)]
        deviations, audit = evaluate(events, SCHEDULES)
        self.assertEqual({key[-1]: value for key, value in deviations.items()}, {"arrival": 60, "departure": -60})
        self.assertEqual(audit, {})

    def test_repeated_actuals_coalesce_including_equivalent_timestamp_offsets(self):
        replay = replace(EVENT, occurred_at=EVENT.occurred_at.astimezone(LA),
                         recorded_at=EVENT.recorded_at + timedelta(minutes=15))
        deviations, audit = evaluate([EVENT, replay], SCHEDULES)
        self.assertEqual(list(deviations.values()), [-120])
        self.assertEqual(audit, {"duplicate_rows": 1})

    def test_conflicting_actuals_exclude_group_in_both_input_orders(self):
        conflict = replace(EVENT, occurred_at=EVENT.occurred_at + timedelta(seconds=5))
        for rows in ([EVENT, conflict, EVENT], [conflict, EVENT, EVENT]):
            self.assertEqual(evaluate(rows, SCHEDULES),
                             ({}, {"duplicate_rows": 1, "conflicting_event_keys": 1}))

    def test_predictions_and_unknown_provenance_never_match(self):
        for evidence in ("prediction", "inherited_delay", "unknown"):
            with self.subTest(evidence=evidence):
                self.check_rejected(replace(EVENT, evidence=evidence), "unverified_event")
        deviations, audit = evaluate([EVENT, replace(EVENT, evidence="prediction")], SCHEDULES)
        self.assertEqual(list(deviations.values()), [-120])
        self.assertEqual(audit, {"unverified_event": 1})

    def test_future_missing_and_naive_occurrences_are_excluded(self):
        self.check_rejected(replace(EVENT, occurred_at=EVENT.recorded_at + timedelta(seconds=1)),
                            "future_occurrence")
        self.check_rejected(replace(EVENT, occurred_at=None), "missing_absolute_time")
        self.check_rejected(replace(EVENT, occurred_at=EVENT.occurred_at.replace(tzinfo=None)),
                            "missing_absolute_time")

    def test_ambiguous_feed_trip_or_stop_is_excluded(self):
        extra = replace(NOV26, version="other")
        self.check_rejected(EVENT, "schedule_ambiguous", (NOV26, extra))
        self.check_deviation(replace(EVENT, feed_version="v1"), -120, (NOV26, extra))
        self.check_rejected(EVENT, "trip_ambiguous", (replace(NOV26, trips=(TRIP, TRIP)),))
        repeated = replace(TRIP, stops=(*STOPS, STOPS[1]))
        self.check_rejected(EVENT, "stop_ambiguous", (replace(NOV26, trips=(repeated,)),))

    def test_unusable_schedule_or_relationship_is_excluded(self):
        self.check_rejected(replace(EVENT, trip_id="missing"), "trip_missing")
        self.check_rejected(replace(EVENT, trip_id="frequency"), "unsupported_trip")
        self.check_rejected(replace(EVENT, trip_relationship="canceled"), "unsupported_relationship")
        self.check_rejected(replace(EVENT, stop_relationship="skipped"), "unsupported_relationship")
        self.check_rejected(replace(EVENT, stop_relationship="no_data"), "unsupported_relationship")
        for sequence, stop_id in ((100, "approximate"), (110, "missing_time")):
            self.check_rejected(replace(EVENT, sequence=sequence, stop_id=stop_id), "no_exact_schedule_time")


if __name__ == "__main__":
    unittest.main()
