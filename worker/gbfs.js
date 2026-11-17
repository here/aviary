// Cloudflare Worker: archives shared bike and scooter availability (GBFS) around the study corridors.
//
// Every 10 minutes it reads each operator's public GBFS feed, keeps the vehicles and stations inside
// the study area, and stores one gzipped JSON snapshot in R2:
//     gbfs/YYYY-MM-DD/HH/gbfs_YYYY-MM-DDTHHMM.json.gz
// GBFS has no history, so availability before a street project can only be known if it was recorded.
// Vehicle ids rotate by design, so this shows where vehicles are parked, not individual trips.

// Study area: Hollywood, East Hollywood, Silver Lake, Echo Park, Downtown edge, Vermont corridor.
const BBOX = { south: 33.92, north: 34.115, west: -118.36, east: -118.225 };

// Auto-discovery files. Operators move these; /gbfs/discover lists what MobilityData's catalog has for LA.
// Lime is not here: its Los Angeles feed address returned 404 in November 2026 and it is absent from the catalog.
const SYSTEMS = {
  metro_bike_share: "https://gbfs.bcycle.com/bcycle_lametro/gbfs.json",
  bird: "https://mds.bird.co/gbfs/v2/public/los-angeles/gbfs.json",
  lyft: "https://s3.amazonaws.com/lyft-lastmile-production-iad/lbs/lax/gbfs.json",
  spin: "https://mds.bird.co/gbfs/v2/public/provider/spin/los_angeles/gbfs.json",
  veo: "https://cluster-prod.veoride.com/api/shares/name/xla/gbfs",
};
const CATALOG = "https://raw.githubusercontent.com/MobilityData/gbfs/master/systems.csv";

const inBox = (lat, lon) => lat >= BBOX.south && lat <= BBOX.north && lon >= BBOX.west && lon <= BBOX.east;
const getJson = async (url) => {
  const r = await fetch(url, { headers: { accept: "application/json", "user-agent": "gbfs-archiver" }, signal: AbortSignal.timeout(20000) });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

async function readSystem(discoveryUrl) {
  const disc = await getJson(discoveryUrl);
  const d = disc.data || {};
  const feeds = (d.en || d.feeds ? (d.en || d).feeds : Object.values(d)[0]?.feeds) || [];
  const url = (name) => feeds.find((f) => f.name === name)?.url;
  const out = { version: disc.version || null, vehicles: [], stations: [] };

  const vehiclesUrl = url("vehicle_status") || url("free_bike_status");
  if (vehiclesUrl) {
    const v = await getJson(vehiclesUrl);
    out.last_updated = v.last_updated;
    for (const b of v.data?.vehicles || v.data?.bikes || []) {
      if (typeof b.lat === "number" && inBox(b.lat, b.lon)) {
        out.vehicles.push({ id: b.vehicle_id || b.bike_id, lat: b.lat, lon: b.lon, type: b.vehicle_type_id || null,
          reserved: !!b.is_reserved, disabled: !!b.is_disabled, range_m: b.current_range_meters ?? null });
      }
    }
  }
  const infoUrl = url("station_information"), statusUrl = url("station_status");
  if (infoUrl && statusUrl) {
    const [info, status] = await Promise.all([getJson(infoUrl), getJson(statusUrl)]);
    const st = new Map((status.data?.stations || []).map((s) => [s.station_id, s]));
    for (const s of info.data?.stations || []) {
      if (typeof s.lat === "number" && inBox(s.lat, s.lon)) {
        const x = st.get(s.station_id) || {};
        out.stations.push({ id: s.station_id, name: s.name, lat: s.lat, lon: s.lon,
          bikes: x.num_bikes_available ?? x.num_vehicles_available ?? null, docks: x.num_docks_available ?? null });
      }
    }
  }
  return out;
}

async function snapshot(env, when = new Date()) {
  const iso = when.toISOString();
  const systems = {}, summary = {};
  await Promise.all(Object.entries(SYSTEMS).map(async ([name, url]) => {
    try {
      systems[name] = await readSystem(url);
      summary[name] = { vehicles: systems[name].vehicles.length, stations: systems[name].stations.length };
    } catch (e) {
      summary[name] = { error: String(e.message || e) };
    }
  }));
  const key = `gbfs/${iso.slice(0, 10)}/${iso.slice(11, 13)}/gbfs_${iso.slice(0, 13)}${iso.slice(14, 16)}.json.gz`;
  const stored = Object.keys(systems).length > 0;
  if (stored) {
    const body = new Blob([JSON.stringify({ at: iso, bbox: BBOX, systems })]).stream().pipeThrough(new CompressionStream("gzip"));
    await env.ARCHIVE.put(key, await new Response(body).arrayBuffer(), { httpMetadata: { contentType: "application/json", contentEncoding: "gzip" } });
  }
  const status = { at: iso, key: stored ? key : null, systems: summary };
  await env.ARCHIVE.put("status/gbfs.json", JSON.stringify(status), { httpMetadata: { contentType: "application/json" } });
  return status;
}

const json = (b, s = 200) => new Response(JSON.stringify(b, null, 2), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(snapshot(env, new Date(controller.scheduledTime)));
  },
  // Maintenance routes, served at aviary.herebox.org/gbfs/...: status, run (take a snapshot now), discover (catalog rows for LA).
  async fetch(request, env) {
    const path = new URL(request.url).pathname.replace(/^\/gbfs/, "") || "/";
    if (path === "/status") {
      const o = await env.ARCHIVE.get("status/gbfs.json");
      return json(o ? await o.json() : { at: null, error: "no snapshot yet" });
    }
    if (path === "/run") return json(await snapshot(env));
    if (path === "/discover") {
      const csv = await (await fetch(CATALOG)).text();
      const rows = csv.split("\n").filter((l) => /los angeles|santa monica|west hollywood|, CA/i.test(l) && /^US,/.test(l));
      return new Response(rows.join("\n"), { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    return json({ routes: ["/gbfs/status", "/gbfs/run", "/gbfs/discover"] }, 404);
  },
};
