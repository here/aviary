"""Corridors that are not straight north-south streets: position = miles along a line.

A corridor file (corridors/<id>.json) holds the street's path as lon/lat points, the named
section boundaries, the bus routes that use it, and names for the two directions.
"""
import json
import pathlib

import numpy as np

MI_PER_DEG_LAT = 68.92
ON_LINE_MI = 0.06      # ~100 m: stops and pings further from the path are not on the corridor
SNAP_MI = 0.14         # a trip may fall this short of a boundary and still cover the section


class PolylineCorridor:
    def __init__(self, path: pathlib.Path):
        cfg = json.loads(pathlib.Path(path).read_text())
        self.id, self.name, self.routes = cfg["corridor_id"], cfg["name"], tuple(cfg["routes"])
        self.dir_up, self.dir_down = cfg["directions"]["increasing"], cfg["directions"]["decreasing"]
        line = np.array(cfg["line"], dtype=float)
        self._lat0 = line[:, 1].mean()
        self._xy = self._plane(line[:, 0], line[:, 1])
        seg = np.diff(self._xy, axis=0)
        self._seg, self._len = seg, np.hypot(seg[:, 0], seg[:, 1])
        self._cum = np.concatenate([[0], np.cumsum(self._len)])
        names = [b[0] for b in cfg["breakpoints"]]
        pos, _ = self.locate(np.array([b[2] for b in cfg["breakpoints"]]), np.array([b[1] for b in cfg["breakpoints"]]))
        self.breaks = pos  # miles along the line, increasing
        self.sections = [
            {"corridor_id": self.id, "section_id": f"S{i + 1}", "name": f"{names[i]} to {names[i + 1]}",
             "start_mi": round(float(pos[i]), 3), "end_mi": round(float(pos[i + 1]), 3),
             "length_mi": round(float(pos[i + 1] - pos[i]), 3)}
            for i in range(len(pos) - 1)
        ]
        self.total = {"corridor_id": self.id, "section_id": "corridor", "name": f"{names[0]} to {names[-1]}",
                      "start_mi": round(float(pos[0]), 3), "end_mi": round(float(pos[-1]), 3),
                      "length_mi": round(sum(s["length_mi"] for s in self.sections), 3)}

    def _plane(self, lon, lat):
        return np.column_stack([(np.asarray(lon) - (-118.3)) * MI_PER_DEG_LAT * np.cos(np.radians(self._lat0)),
                                (np.asarray(lat) - self._lat0) * MI_PER_DEG_LAT])

    def locate(self, lat, lon):
        """Return (miles along the line, distance from the line in miles) for each point."""
        p = self._plane(lon, lat)[:, None, :]                      # P x 1 x 2
        a = self._xy[None, :-1, :]                                 # 1 x S x 2
        t = np.clip(((p - a) * self._seg[None]).sum(-1) / np.maximum(self._len ** 2, 1e-12)[None], 0, 1)
        d = np.hypot(*np.moveaxis(p - (a + t[..., None] * self._seg[None]), -1, 0))
        j = d.argmin(1)
        i = np.arange(len(j))
        return self._cum[j] + t[i, j] * self._len[j], d[i, j]
