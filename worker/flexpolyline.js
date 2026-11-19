// HERE Flexible Polyline encoder (2D only), as specified at https://github.com/heremaps/flexible-polyline.
// Used for the `in=corridor:{polyline};r={radius}` filter of HERE Traffic API v7.
const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

function unsigned(v) {
  let out = "";
  while (v > 0x1f) {
    out += CHARS[(v & 0x1f) | 0x20];
    v = Math.floor(v / 32);
  }
  return out + CHARS[v];
}

function signed(v) {
  let u = v < 0 ? -2 * v - 1 : 2 * v; // zig-zag: same as (v << 1) ^ (v >> 63) without 32-bit overflow
  return unsigned(u);
}

// points: [[lat, lng], ...]
export function encode(points, precision = 5) {
  const f = 10 ** precision;
  let out = unsigned(1) + unsigned(precision); // format version 1; no third dimension
  let pLat = 0, pLng = 0;
  for (const [lat, lng] of points) {
    const iLat = Math.round(lat * f), iLng = Math.round(lng * f);
    out += signed(iLat - pLat) + signed(iLng - pLng);
    pLat = iLat; pLng = iLng;
  }
  return out;
}

// Douglas-Peucker on a lon/lat path ([[lon, lat], ...]), tolerance in metres. Keeps corridor URLs short.
export function simplify(line, tolM = 8) {
  const k = 111320, c = Math.cos((line[0][1] * Math.PI) / 180);
  const xy = line.map(([lon, lat]) => [lon * k * c, lat * k]);
  const keep = new Array(line.length).fill(false);
  keep[0] = keep[line.length - 1] = true;
  const stack = [[0, line.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    let worst = -1, at = -1;
    const [ax, ay] = xy[a], [bx, by] = xy[b], dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy) || 1e-9;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs(dy * (xy[i][0] - ax) - dx * (xy[i][1] - ay)) / L;
      if (d > worst) { worst = d; at = i; }
    }
    if (worst > tolM) { keep[at] = true; stack.push([a, at], [at, b]); }
  }
  return line.filter((_, i) => keep[i]);
}
