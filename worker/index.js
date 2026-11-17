// Cloudflare Worker for the Vermont Av speed archive.
//
//  - scheduled(): every minute, listens to LA Metro's public vehicle-position
//    websocket for ~55 s and stores what it hears in R2 as gzipped NDJSON:
//        raw/YYYY-MM-DD/HH/vehicle_positions_YYYY-MM-DDTHHMM.ndjson.gz
//    Messages are stored exactly as received, so no key or parsing is needed.
//  - fetch(): /api/* routes over the archive. Everything else is the static
//    site (built into _site/ by pipeline/build_site.py) served by Workers assets.

const FEED = "wss://api.metro.net/ws/LACMTA/vehicle_positions/";
const LISTEN_MS = 55_000;

function listen(url, ms) {
  return new Promise((resolve) => {
    const lines = [];
    let ws, error = null;
    const done = () => { try { ws && ws.close(); } catch (_) {} resolve({ lines, error }); };
    const timer = setTimeout(done, ms);
    try {
      ws = new WebSocket(url);
      ws.addEventListener("message", (ev) => { if (typeof ev.data === "string") lines.push(ev.data); });
      ws.addEventListener("error", () => { error = "websocket error"; clearTimeout(timer); done(); });
      ws.addEventListener("close", () => { clearTimeout(timer); done(); });
    } catch (e) { error = String(e); clearTimeout(timer); done(); }
  });
}

async function gzip(text) {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

async function collect(env, when = new Date()) {
  const routes = env.ROUTES || "204,754,2,4";
  const { lines, error } = await listen(FEED + routes, LISTEN_MS);
  const iso = when.toISOString();                       // 2026-11-17T04:27:00.000Z
  const key = `raw/${iso.slice(0, 10)}/${iso.slice(11, 13)}/vehicle_positions_${iso.slice(0, 13)}${iso.slice(14, 16)}.ndjson.gz`;
  if (lines.length) {
    await env.ARCHIVE.put(key, await gzip(lines.join("\n") + "\n"), {
      httpMetadata: { contentType: "application/x-ndjson", contentEncoding: "gzip" },
      customMetadata: { messages: String(lines.length), routes },
    });
  }
  const status = { at: iso, key: lines.length ? key : null, messages: lines.length, error };
  await env.ARCHIVE.put("status/latest.json", JSON.stringify(status), { httpMetadata: { contentType: "application/json" } });
  return status;
}

const json = (body, status = 200) => new Response(JSON.stringify(body, null, 2), {
  status, headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*", "cache-control": "no-store" },
});

export default {
  async scheduled(controller, env, ctx) {
    if (!env.ARCHIVE) return; // storage not attached yet
    ctx.waitUntil(collect(env, new Date(controller.scheduledTime)));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    if (request.method !== "GET" && request.method !== "HEAD") return json({ error: "read-only" }, 405);
    if (!env.ARCHIVE) return json({ at: null, messages: 0, error: "archive storage (R2) is not attached yet" }, url.pathname === "/api/status" ? 200 : 503);

    // GET /api/status -> when the collector last ran and what it stored
    if (url.pathname === "/api/status") {
      const obj = await env.ARCHIVE.get("status/latest.json");
      return json(obj ? await obj.json() : { at: null, messages: 0, error: "collector has not run yet" });
    }

    // GET /api/files?prefix=raw/2026-11-17/ -> list archived objects (raw/, daily/, mds/)
    if (url.pathname === "/api/files") {
      const prefix = url.searchParams.get("prefix") || "daily/";
      if (!/^(raw|daily|mds)\//.test(prefix)) return json({ error: "prefix must start with raw/, daily/ or mds/" }, 400);
      const page = await env.ARCHIVE.list({ prefix, limit: 1000, cursor: url.searchParams.get("cursor") || undefined });
      return json({
        prefix,
        files: page.objects.map((o) => ({ key: o.key, bytes: o.size, uploaded: o.uploaded, url: `/api/file/${o.key}` })),
        next_cursor: page.truncated ? page.cursor : null,
      });
    }

    // GET /api/file/<key> -> download one archived object
    if (url.pathname.startsWith("/api/file/")) {
      const key = decodeURIComponent(url.pathname.slice("/api/file/".length));
      if (!/^(raw|daily|mds)\//.test(key)) return json({ error: "not found" }, 404);
      const obj = await env.ARCHIVE.get(key);
      if (!obj) return json({ error: "not found" }, 404);
      return new Response(obj.body, {
        headers: { "content-type": "application/gzip", "content-disposition": `attachment; filename="${key.split("/").pop()}"`, etag: obj.httpEtag, "access-control-allow-origin": "*" },
      });
    }
    return json({ error: "not found", routes: ["/api/status", "/api/files?prefix=daily/", "/api/file/<key>"] }, 404);
  },
};
