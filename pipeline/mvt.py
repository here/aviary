"""Minimal Mapbox Vector Tile decoder (spec v2), standard library only.

TomTom's traffic flow tiles are Mapbox vector tiles. The usual Python decoder (`mapbox-vector-tile`) pins an older
protobuf than `gtfs-realtime-bindings` needs, so this reads the protobuf wire format directly. It handles what the
traffic tiles use: layers, string keys, typed values, and point / line / polygon geometry.

    from mvt import decode
    layers = decode(tile_bytes)          # {"Traffic flow": {"extent": 4096, "features": [...]}}
    feature = layers["Traffic flow"]["features"][0]
    feature["properties"], feature["type"], feature["geometry"]   # geometry: list of parts, each a list of (x, y)

Coordinates are tile pixels with the origin at the top left (y grows downwards), 0..extent.
"""
import struct

GEOM_TYPES = {1: "Point", 2: "LineString", 3: "Polygon"}


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if b < 0x80:
            return result, i
        shift += 7


def _fields(buf: bytes):
    """Yield (field number, wire type, value) for one protobuf message."""
    i, n = 0, len(buf)
    while i < n:
        key, i = _varint(buf, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            val, i = _varint(buf, i)
        elif wire == 1:
            val, i = buf[i:i + 8], i + 8
        elif wire == 2:
            size, i = _varint(buf, i)
            val, i = buf[i:i + size], i + size
        elif wire == 5:
            val, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"unsupported wire type {wire}")
        yield field, wire, val


def _packed(buf: bytes) -> list[int]:
    out, i = [], 0
    while i < len(buf):
        v, i = _varint(buf, i)
        out.append(v)
    return out


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _value(buf: bytes):
    for field, wire, val in _fields(buf):
        if field == 1:
            return val.decode("utf-8")
        if field == 2:
            return struct.unpack("<f", val)[0]
        if field == 3:
            return struct.unpack("<d", val)[0]
        if field in (4, 5):
            return val if field == 5 or val < 1 << 63 else val - (1 << 64)
        if field == 6:
            return _zigzag(val)
        if field == 7:
            return bool(val)
    return None


def _geometry(cmds: list[int]) -> list[list[tuple[int, int]]]:
    parts, part, x, y, i = [], None, 0, 0, 0
    while i < len(cmds):
        cmd, count = cmds[i] & 7, cmds[i] >> 3
        i += 1
        if cmd in (1, 2):  # MoveTo, LineTo
            for _ in range(count):
                x += _zigzag(cmds[i])
                y += _zigzag(cmds[i + 1])
                i += 2
                if cmd == 1:
                    part = [(x, y)]
                    parts.append(part)
                else:
                    part.append((x, y))
        elif cmd == 7 and part:  # ClosePath
            part.append(part[0])
    return parts


def decode(tile: bytes) -> dict:
    layers = {}
    for field, _, layer_buf in _fields(tile):
        if field != 3:
            continue
        name, extent, keys, values, raw = "", 4096, [], [], []
        for f, _, v in _fields(layer_buf):
            if f == 1:
                name = v.decode("utf-8")
            elif f == 2:
                raw.append(v)
            elif f == 3:
                keys.append(v.decode("utf-8"))
            elif f == 4:
                values.append(_value(v))
            elif f == 5:
                extent = v
        features = []
        for fb in raw:
            tags, gtype, geom, fid = [], 0, [], None
            for f, wire, v in _fields(fb):
                if f == 1:
                    fid = v
                elif f == 2:
                    tags = _packed(v) if wire == 2 else [v]
                elif f == 3:
                    gtype = v
                elif f == 4:
                    geom = _packed(v) if wire == 2 else [v]
            props = {keys[tags[j]]: values[tags[j + 1]] for j in range(0, len(tags) - 1, 2)}
            features.append({"id": fid, "properties": props, "type": GEOM_TYPES.get(gtype, "Unknown"), "geometry": _geometry(geom)})
        layers[name] = {"extent": extent, "features": features}
    return layers
