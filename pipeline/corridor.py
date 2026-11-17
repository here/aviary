"""Shared definition of the Vermont Av study corridor.

Vermont Av runs due north-south at longitude ~-118.2914, so position along the
corridor is simply latitude. Sections are bounded by major cross streets.
"""

ROUTES = ("204", "754")  # 204 = Metro Local, 754 = Metro Rapid (same street)
TIMEZONE = "America/Los_Angeles"

VERMONT_LON = -118.2914
LON_TOLERANCE = 0.0030  # ~275 m either side: on-street stops and GPS pings only
MILES_PER_DEG_LAT = 68.92  # at 34 N

# (name, latitude) of the section boundaries, north to south.
BREAKPOINTS = [
    ("Sunset Bl", 34.0980),
    ("Wilshire Bl", 34.0621),
    ("Washington Bl", 34.0404),
    ("Exposition Bl", 34.0186),
    ("Slauson Av", 33.9890),
    ("Manchester Av", 33.9604),
    ("Athens Station (I-105)", 33.9285),
]

SECTIONS = []
for _i, ((_n0, _lat0), (_n1, _lat1)) in enumerate(zip(BREAKPOINTS, BREAKPOINTS[1:]), start=1):
    SECTIONS.append(
        {
            "section_id": f"S{_i}",
            "name": f"{_n0} to {_n1}",
            "north_lat": _lat0,
            "south_lat": _lat1,
            "length_mi": round((_lat0 - _lat1) * MILES_PER_DEG_LAT, 3),
        }
    )

CORRIDOR = {
    "section_id": "corridor",
    "name": f"{BREAKPOINTS[0][0]} to {BREAKPOINTS[-1][0]}",
    "north_lat": BREAKPOINTS[0][1],
    "south_lat": BREAKPOINTS[-1][1],
    "length_mi": round(sum(s["length_mi"] for s in SECTIONS), 3),
}

# How far (degrees latitude, ~220 m) a trip may fall short of a boundary and
# still be counted as covering the section; the end stop's time is used.
SNAP_TOLERANCE = 0.0020
