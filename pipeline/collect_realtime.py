#!/usr/bin/env python3
"""Collect live LA Metro vehicle positions for the Vermont Av lines.

Connects to the public LA Metro websocket (wss://api.metro.net) and appends
every GTFS-realtime VehiclePosition message it receives to an NDJSON file,
one message per line, exactly as received plus a `received_at` epoch field.

    python pipeline/collect_realtime.py --minutes 55 --out data/raw

Run it from cron / a scheduler once an hour to build an observed-speed archive;
`build_observed.py` turns the raw files into hourly speeds.
"""
import argparse
import asyncio
import datetime as dt
import json
import pathlib
import time

import websockets

URL = "wss://api.metro.net/ws/LACMTA/vehicle_positions/{routes}"


async def collect(routes: str, minutes: float, out_dir: pathlib.Path) -> int:
    deadline = time.time() + minutes * 60
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    while time.time() < deadline:
        try:
            async with websockets.connect(URL.format(routes=routes), open_timeout=20) as ws:
                while time.time() < deadline:
                    msg = await asyncio.wait_for(ws.recv(), timeout=90)
                    rec = json.loads(msg)
                    rec["received_at"] = round(time.time(), 1)
                    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
                    with open(out_dir / f"vehicle_positions_{day}.ndjson", "a") as fh:
                        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
                    count += 1
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as exc:
            print(f"reconnecting after {exc!r}", flush=True)
            await asyncio.sleep(5)
    return count


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--routes", default="204,754", help="comma-separated route codes")
    ap.add_argument("--minutes", type=float, default=55)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/raw"))
    a = ap.parse_args()
    n = asyncio.run(collect(a.routes, a.minutes, a.out))
    print(f"wrote {n} messages")
