#!/usr/bin/env python3
"""Convert archived Swiftly vehicle-position snapshots into the ping format the roll-ups read.

The collector Worker stores Swiftly's GTFS-realtime protobuf every minute under swiftly/vp/. Each
vehicle entity is written out as one JSON line in the same shape as LA Metro's websocket messages
(the two feeds carry identical vehicle records), plus `route_code` and `source: "swiftly"`, so
build_observed.py and build_observed_corridor.py read both feeds unchanged and drop duplicates on
(vehicle id, timestamp).

    python pipeline/fetch_archive.py --prefix swiftly/vp/2026-11-18/ --out run
    python pipeline/swiftly_to_pings.py --in run/swiftly/vp --out run/raw/swiftly

Writes one vehicle_positions_swiftly_YYYY-MM-DDTHH.ndjson.gz per UTC hour, keeping only the routes
used by Vermont Av and the corridors in corridors/.
"""
import argparse
import gzip
import json
import pathlib
import re
from collections import defaultdict

from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2

VERMONT_ROUTES = {"204", "754"}


def study_routes(corridor_dir: pathlib.Path) -> set[str]:
    routes = set(VERMONT_ROUTES)
    for path in corridor_dir.glob("*.json"):
        routes.update(json.loads(path.read_text()).get("routes", []))
    return routes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in", dest="src", type=pathlib.Path, required=True, help="folder of swiftly_vp_*.pb.gz, searched recursively")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--corridors", type=pathlib.Path, default=pathlib.Path("corridors"))
    a = ap.parse_args()
    keep = study_routes(a.corridors)

    by_hour: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    files = sorted(a.src.rglob("swiftly_vp_*.pb.gz"))
    for path in files:
        hour = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2})\d{2}\.pb\.gz$", path.name)
        if not hour:
            continue
        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(gzip.open(path).read())
        except Exception as exc:  # one damaged snapshot should not stop the rest
            print(f"skipped {path.name}: {exc!r}")
            continue
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            route = entity.vehicle.trip.route_id.split("-")[0]
            vid = entity.vehicle.vehicle.id or entity.id
            stamp = str(entity.vehicle.timestamp)
            if route not in keep or (vid, stamp) in seen:
                continue
            seen.add((vid, stamp))
            rec = MessageToDict(entity)
            rec["route_code"], rec["source"] = route, "swiftly"
            by_hour[hour.group(1)].append(json.dumps(rec, separators=(",", ":")))

    a.out.mkdir(parents=True, exist_ok=True)
    for hour, lines in sorted(by_hour.items()):
        with gzip.open(a.out / f"vehicle_positions_swiftly_{hour}.ndjson.gz", "wt") as fh:
            fh.write("\n".join(lines) + "\n")
    print(f"{len(files)} snapshots -> {len(seen):,} pings on {len(keep)} routes in {len(by_hour)} hourly files")


if __name__ == "__main__":
    main()
