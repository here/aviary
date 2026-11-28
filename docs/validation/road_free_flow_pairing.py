"""Reproduce the pinned hourly inventory and synthetic road pairing examples."""

import csv
import math
import subprocess
from collections import Counter, defaultdict
from fractions import Fraction as F

PIN = "6636c6c76ec2aba9797838a69bf7546cae6bc4ba"
paths = [p for p in subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", PIN, "data"], text=True
).splitlines() if "/traffic/" in p and p.endswith("_traffic_2026-11.csv")]
assert len(paths) == 14
groups = defaultdict(Counter)
keys = set()

def positive(row, name):
    value = float(row[name] or "nan")
    return math.isfinite(value) and value > 0

for path in paths:
    rows = subprocess.check_output(["git", "show", f"{PIN}:{path}"], text=True)
    for row in csv.DictReader(rows.splitlines()):
        source, corridor, section, direction, hour = (
            row[k] for k in ("source", "corridor_id", "section_id", "direction", "hour_start_utc")
        )
        key = (source, corridor, section, direction, hour)
        assert key not in keys
        keys.add(key)
        n = int(row["n_snapshots"])
        coverage = float(row["coverage"])
        assert n > 0 and 0 <= coverage <= 1
        closure = float(row["closed_share"])
        valid = all(positive(row, k) for k in (
            "speed_mph", "free_flow_mph", "travel_time_min", "length_mi"
        ))
        eligible = valid and coverage >= 0.8 and closure == 0
        c = groups[source, "corridor" if section == "corridor" else "section"]
        c["rows"] += 1
        c["numeric"] += valid
        c["one_snapshot_numeric"] += valid and n == 1
        c["screened"] += eligible
        c["one_snapshot_screened"] += eligible and n == 1
        c["full_one_snapshot_screened"] += eligible and n == 1 and coverage == 1
        c["over_cadence_rows"] += n > (1 if source == "here_traffic_flow" else 4)
        if "2026-11-20" <= hour < "2026-11-25":
            if source == "tomtom_traffic_flow" or int(hour[11:13]) % 3 in (0, 1):
                c["window_numeric"] += valid
                c["window_screened"] += eligible

for key, counts in sorted(groups.items()):
    print(key, dict(counts))
assert len(keys) == 20_995
assert sum(c["numeric"] for c in groups.values()) == 19_902

# Each piece is a disjoint interval specified by length, current mph, and baseline mph.
def length_and_time(pieces, field):
    selected = [piece for piece in pieces if piece[field] is not None]
    return sum(p[0] for p in selected), 60 * sum(p[0] / F(p[field]) for p in selected)

def published(snapshots):
    def mph(pieces, field):
        length, time = length_and_time(pieces, field)
        return 60 * length / time if time else None
    def harmonic(values):
        values = [v for v in values if v is not None]
        return len(values) / sum(1 / v for v in values)
    return tuple(harmonic([mph(p, field) for p in snapshots]) for field in (1, 2))

def paired(pieces):
    common = [p for p in pieces if p[1] is not None and p[2] is not None]
    if common:
        length, current = length_and_time(common, 1)
        _, free = length_and_time(common, 2)
        return length, current, free, current - free

a = [(F(1, 4), 10, 30), (F(3, 4), 20, None)]
b = [(F(1, 4), 10, None), (F(3, 4), 20, 30)]
assert published([a]) == published([b]) == (F(16), F(30))
assert paired(a) == (F(1, 4), F(3, 2), F(1, 2), F(1))
assert paired(b) == (F(3, 4), F(9, 4), F(3, 2), F(3, 4))
assert (paired(a)[3] / paired(a)[0], paired(b)[3] / paired(b)[0]) == (4, 1)
print("Link counterexample:", published([a]), paired(a), paired(b))

c = [[(F(1), 10, 30)], [(F(1), 20, None)]]
d = [[(F(1), 10, None)], [(F(1), 20, 30)]]
assert published(c) == published(d) == (F(40, 3), F(30))
assert [p[3] for snap in c if (p := paired(snap))] == [4]
assert [p[3] for snap in d if (p := paired(snap))] == [1]
print("Snapshot counterexample:", published(c), 4, 1)

# Same two fully paired, fixed-support snapshots. Mean time difference equals the
# difference of harmonic-speed-derived times; an arithmetic mph mean does not.
full = [[(F(1), 10, 30)], [(F(1), 20, 30)]]
assert sum(paired(s)[3] for s in full) / 2 == F(5, 2)
current, free = published(full)
assert 60 / current - 60 / free == F(5, 2)
assert 60 / F(15) - 60 / F(30) == 2

# Variable support: averaging pace equally and pooling matched miles answer
# different questions. An equal-snapshot covered-distance delay also differs.
assert (paired(a)[3] + paired(b)[3]) / 2 == F(7, 8)
assert (paired(a)[3] / paired(a)[0] + paired(b)[3] / paired(b)[0]) / 2 == F(5, 2)
assert (paired(a)[3] + paired(b)[3]) / (paired(a)[0] + paired(b)[0]) == F(7, 4)

# Two overlapping projected intervals sum to 1.1 mi but cover only 0.8 mi.
intervals = [(F(0), F(6, 10)), (F(3, 10), F(8, 10))]
assert sum(hi - lo for lo, hi in intervals) == F(11, 10)
assert max(hi for _, hi in intervals) - min(lo for lo, _ in intervals) == F(8, 10)
print("Weighting and interval tests passed.")

# A corridor must use the intersection of eligible section snapshot IDs.
section_1 = {"00": F(2), "15": F(4)}
section_2 = {"15": F(1), "30": F(7)}
common_ids = section_1.keys() & section_2.keys()
assert common_ids == {"15"}
assert sum(section_1[s] + section_2[s] for s in common_ids) / len(common_ids) == 5
assert sum(section_1.values()) / 2 + sum(section_2.values()) / 2 == 7
assert paired([(F(1), 40, 30)])[3] == -F(1, 2)
print("Same-snapshot corridor intersection and signed excess tests passed.")
