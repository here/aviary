// Cloudflare Worker: archives general-traffic speeds (HERE Traffic API v7 flow) on the study streets.
//
// Every 30 minutes it asks HERE for current flow on every road segment inside three boxes (Vermont Av;
// Hollywood Bl plus Fountain Av; Sunset Bl / Cesar Chavez Av) and stores each response, gzipped, in R2:
//     traffic/here/YYYY-MM-DD/HH/here_<box>_YYYY-MM-DDTHHMM.json.gz
// Each segment carries current speed, free-flow speed, jam factor and its shape, so a later roll-up can match
// segments to the corridor sections. Three boxes x 48 runs a day is about 4,300 requests a month.
// Does nothing until the HERE_API_KEY secret is set.
//
// Routes (on aviary.herebox.org): /traffic/status, /traffic/run (collect now).

import hollywood from "../corridors/hollywood.json";
import fountain from "../corridors/fountain.json";
import sunset from "../corridors/sunset.json";

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
};

async function gzip(text) {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

async function collect(env, when = new Date()) {
  const iso = when.toISOString(), day = iso.slice(0, 10), hour = iso.slice(11, 13), stamp = `${iso.slice(0, 13)}${iso.slice(14, 16)}`;
  const status = { at: iso, boxes: {} };
  if (!env.HERE_API_KEY) {
    status.error = "HERE_API_KEY secret not set";
  } else {
    for (const [name, b] of Object.entries(BOXES)) {
      const q = new URLSearchParams({ in: `bbox:${b.map((v) => v.toFixed(5)).join(",")}`, locationReferencing: "shape", apiKey: env.HERE_API_KEY });
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
    const path = new URL(request.url).pathname.replace(/^\/traffic/, "") || "/";
    if (path === "/status") {
      const o = await env.ARCHIVE.get("status/traffic.json");
      return json(o ? await o.json() : { at: null, error: env.HERE_API_KEY ? "not run yet" : "HERE_API_KEY secret not set", boxes: BOXES });
    }
    if (path === "/run") return json(await collect(env));
    return json({ routes: ["/traffic/status", "/traffic/run"], boxes: BOXES }, 404);
  },
};
