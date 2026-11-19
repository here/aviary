// Cloudflare Worker: archives general-traffic speeds on the study streets from two providers.
//
// TomTom (Orbis Maps Traffic API v2, Vector Flow Tiles; billed as "Traffic Flow & Incidents API Vector Tiles",
// free 200,000 a month), every 15 minutes, if TOMTOM_API_KEY is set:
//     traffic/tomtom/YYYY-MM-DD/HH/tomtom_flow_YYYY-MM-DDTHHMM.json.gz
//   One gzipped JSON per run: {"at", "zoom", "attributes", "tiles": {"z/x/y": "<base64 Mapbox vector tile>"}}.
//   30 zoom-14 tiles cover the boxes below (see docs/FREE_TIERS.md before adding more). Each road piece in a tile carries absolute_speed (km/h),
//   relative_speed (current / free-flow), road_category, road_closure, part_of_two_way_road and an OpenLR
//   location reference. Only primary, secondary and tertiary roads are requested. Decoding happens later in
//   Python, not here, to stay inside the Worker's CPU limit.
//
// HERE (Traffic API v7 flow), every 90 minutes, if HERE_API_KEY is set: current flow on the roads along each study
// street, using the corridor filter (the street's path, Flexible Polyline encoded, radius 40 m), one request per
// street (7), stored gzipped in R2:
//     traffic/here/YYYY-MM-DD/HH/here_<corridor_id>_YYYY-MM-DDTHHMM.json.gz
// Each flow item carries current speed, free-flow speed, jam factor, confidence and its shape (links), so
// pipeline/build_traffic.py --provider here can match links to the corridor sections. Free plan: 5,000 a month.
//
// Routes (on aviary.herebox.org): /traffic/status, /traffic/run (collect now; add ?here=1 to include HERE off-schedule,
// which costs 7 HERE requests).
// A provider without a key is skipped.

import hollywood from "../corridors/hollywood.json";
import fountain from "../corridors/fountain.json";
import sunset from "../corridors/sunset.json";
import pico from "../corridors/pico.json";
import olympic from "../corridors/olympic.json";
import westwood from "../corridors/westwood.json";
import { encode, simplify } from "./flexpolyline.js";

const FLOW = "https://data.traffic.hereapi.com/v7/flow";
const PAD = 0.002; // degrees (~200 m) around each street's path

function bbox(...lines) {
  const pts = lines.flat();
  const lons = pts.map((p) => p[0]), lats = pts.map((p) => p[1]);
  return [Math.min(...lons) - PAD, Math.min(...lats) - PAD, Math.max(...lons) + PAD, Math.max(...lats) + PAD];
}

// Vermont Av is defined in pipeline/corridor.py: longitude -118.2914, Sunset Bl (34.0980) to Athens Station (33.9285).
const BOXES = {
  vermont: [-118.2944, 33.9265, -118.2884, 34.1000],
  hollywood_fountain: bbox(hollywood.line, fountain.line),
  sunset: bbox(sunset.line),
  pico_olympic: bbox(pico.line, olympic.line), // Olympic Bl is the control street for Pico Bl
  westwood: bbox(westwood.line),
};

// HERE corridor filter: one request per street along its own path, so only roads within HERE_RADIUS_M of the street
// come back (cross streets are dropped later by the roll-up). Paths are simplified to keep the URL under HERE's
// 1,000-character limit. Seven streets every 90 minutes is 16 x 7 x 30 = about 3,400 requests a month, inside
// HERE's free 5,000 a month for Traffic; hourly would be about 5,000 and too close.
const HERE_RADIUS_M = 40;
const HERE_EVERY_MIN = 90;
const VERMONT_LINE = [[-118.2919, 34.1010], [-118.2917, 33.9235]]; // as VERMONT in pipeline/build_traffic.py
const HERE_CORRIDORS = Object.fromEntries(
  [["vermont", VERMONT_LINE], ...[hollywood, fountain, sunset, pico, olympic, westwood].map((c) => [c.corridor_id, c.line])]
    .map(([id, line]) => [id, encode(simplify(line).map(([lon, lat]) => [lat, lon]))]),
);

// Slippy-map tiles covering a box at a zoom level.
function tilesFor(b, z) {
  const n = 2 ** z;
  const tx = (lon) => Math.floor(((lon + 180) / 360) * n);
  const ty = (lat) => Math.floor(((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n);
  const out = [];
  for (let x = tx(b[0]); x <= tx(b[2]); x++) for (let y = ty(b[3]); y <= ty(b[1]); y++) out.push(`${z}/${x}/${y}`);
  return out;
}
const TT_ZOOM = 14;
const TT_TILES = [...new Set(Object.values(BOXES).flatMap((b) => tilesFor(b, TT_ZOOM)))];
const TT_ATTRIBUTES = "tags(absolute_speed,relative_speed,road_category,road_closure,part_of_two_way_road,openlr),roadCategories(primary,secondary,tertiary)";
const TT_FLOW = "https://api.tomtom.com/maps/orbis/traffic/flow/vector/tile/";

function base64(buf) {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

async function collectTomTom(env, iso, day, hour, stamp) {
  if (!env.TOMTOM_API_KEY) return { error: "TOMTOM_API_KEY secret not set" };
  const q = new URLSearchParams({ apiVersion: "2", attributes: TT_ATTRIBUTES });
  const tiles = {}, errors = {};
  let bytes = 0;
  await Promise.all(TT_TILES.map(async (t) => {
    try {
      const r = await fetch(`${TT_FLOW}${t}?${q}`, { headers: { "TomTom-Api-Key": env.TOMTOM_API_KEY }, signal: AbortSignal.timeout(20000) });
      if (!r.ok) throw new Error(`HTTP ${r.status} ${(await r.text()).slice(0, 120)}`);
      const buf = await r.arrayBuffer();
      bytes += buf.byteLength;
      tiles[t] = base64(buf);
    } catch (e) {
      errors[t] = String(e.message || e);
    }
  }));
  const status = { tiles: Object.keys(tiles).length, of: TT_TILES.length, bytes, errors: Object.keys(errors).length ? errors : undefined };
  if (Object.keys(tiles).length) {
    const key = `traffic/tomtom/${day}/${hour}/tomtom_flow_${stamp}.json.gz`;
    await env.ARCHIVE.put(key, await gzip(JSON.stringify({ at: iso, zoom: TT_ZOOM, attributes: TT_ATTRIBUTES, tiles })),
      { httpMetadata: { contentType: "application/json", contentEncoding: "gzip" } });
    status.key = key;
  }
  return status;
}

async function gzip(text) {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

async function collect(env, when = new Date(), forceHere = false) {
  const iso = when.toISOString(), day = iso.slice(0, 10), hour = iso.slice(11, 13), stamp = `${iso.slice(0, 13)}${iso.slice(14, 16)}`;
  const status = { at: iso, tomtom: await collectTomTom(env, iso, day, hour, stamp), boxes: {} };
  if (!env.HERE_API_KEY) {
    status.here = "HERE_API_KEY secret not set";
  } else if (!forceHere && ((when.getUTCHours() * 60 + when.getUTCMinutes()) % HERE_EVERY_MIN) !== 0) {
    status.here = `runs every ${HERE_EVERY_MIN} minutes from 00:00 UTC (free plan: 5,000 requests a month)`;
  } else {
    status.here = "corridor filter, radius " + HERE_RADIUS_M + " m";
    for (const [name, poly] of Object.entries(HERE_CORRIDORS)) {
      const q = new URLSearchParams({ in: `corridor:${poly};r=${HERE_RADIUS_M}`, locationReferencing: "shape", apiKey: env.HERE_API_KEY });
      try {
        const r = await fetch(`${FLOW}?${q}`, { signal: AbortSignal.timeout(25000) });
        const text = await r.text();
        if (!r.ok) throw new Error(`HTTP ${r.status} ${text.slice(0, 160)}`);
        const key = `traffic/here/${day}/${hour}/here_${name}_${stamp}.json.gz`;
        await env.ARCHIVE.put(key, await gzip(text), { httpMetadata: { contentType: "application/json", contentEncoding: "gzip" } });
        let segments = null;
        try { segments = JSON.parse(text).results?.length ?? null; } catch (_) {}
        status.boxes[name] = { key, bytes: text.length, segments };
      } catch (e) {
        status.boxes[name] = { error: String(e.message || e) };
      }
    }
  }
  await env.ARCHIVE.put("status/traffic.json", JSON.stringify(status), { httpMetadata: { contentType: "application/json" } });
  return status;
}

const json = (b, s = 200) => new Response(JSON.stringify(b, null, 2), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(collect(env, new Date(controller.scheduledTime)));
  },
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/traffic/, "") || "/";
    if (path === "/status") {
      const o = await env.ARCHIVE.get("status/traffic.json");
      return json(o ? await o.json() : { at: null, error: "not run yet", tomtom_key: !!env.TOMTOM_API_KEY, here_key: !!env.HERE_API_KEY, tiles: TT_TILES });
    }
    if (path === "/run") return json(await collect(env, new Date(), url.searchParams.get("here") === "1"));
    return json({ routes: ["/traffic/status", "/traffic/run"], boxes: BOXES, here_corridors: HERE_CORRIDORS, tomtom_tiles: TT_TILES }, 404);
  },
};
