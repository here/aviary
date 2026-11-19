# Free tiers and usage

What each service allows without paying, what this project uses, and how much headroom is left. Written
2026-11-19 after adding Pico Bl. **Re-check this file whenever a collector, tile box, polling interval or street is
added**, because those are what move the numbers.

Limits marked "check" come from search summaries or memory and have not been confirmed on the provider's own page.
Confirm them in the provider's dashboard before relying on them.

## Summary

| Service | Free allowance | This project uses | Headroom | Watch |
|---|---|---|---|---|
| TomTom Orbis Maps Traffic API v2, **Vector Flow Tiles** | 200,000 a month, shared with incident vector tiles (pricing line item "Traffic Flow & Incidents API Vector Tiles") | 30 tiles × 96 runs = 2,880 a day, **about 86,000 a month** | About 43% of the free allowance used | Each new street adds 1 to 4 zoom-14 tiles, about 3,000 to 12,000 a month. Room for roughly 35 more tiles at the current 15-minute interval |
| TomTom Traffic Incidents API, **Incident Details** (non-tile) | 2,500 a month (line item "Traffic Incidents API Details") | Not used yet (roadmap E2) | n/a | **Polling every 15 minutes would be 2,880 a month, over the free allowance.** Poll every 20 minutes (2,160 a month), or read incidents from the incident vector tiles, which share the 200,000 tile allowance |
| Swiftly (LA Metro realtime) | 180 requests per 15 minutes per key | Vehicle positions every minute plus trip updates every 15 minutes = **16 per 15 minutes** | About 11× | Requests are not per street, so adding Pico costs nothing. Ask Swiftly about storage and redistribution terms |
| LA Metro websocket | No key, no published limit | One connection a minute (lines 204, 754, 2, 4) | n/a | Line 30 (Pico) comes from Swiftly only |
| Cloudflare Workers (free plan) | 100,000 requests a day; 5 cron triggers per account; 10 ms CPU per invocation (check) | 3 cron Workers: collector every minute, GBFS every 10 minutes, traffic every 15 minutes = **~1,680 runs a day**, plus page and API visits | Wide on requests; **2 cron triggers left** | CPU per run is the tight limit (gzipping a minute of messages). A new collector should share an existing cron rather than add a fourth or fifth |
| Cloudflare R2 storage | 10 GB stored; 1 million Class A (writes, lists) and 10 million Class B (reads) operations a month; no egress fees (check on Cloudflare's pricing page) | Storage grows ~3.5 GB a month, almost all Swiftly snapshots (`swiftly/`, no expiry). Writes ~5,000 a day (~150,000 a month). Reads: the hourly workflow re-downloads two days of minute files each run, **~6,000 objects an hour, ~4.3 million a month** | Storage runs out around **February 2027** (roadmap B2). Reads at ~43% of the free allowance | Reads double if the workflow window grows to four days. To cut them, cache downloads between runs or fetch only new hours |
| GitHub Actions and Pages | Public repository: standard runners free with no minute cap; Pages free | Hourly publish run (~5 to 10 minutes), weekly Cal-ITP refresh | n/a | Scheduled runs are sometimes dropped (roadmap D1). Keep data commits small: the repository grows with every monthly CSV |
| Google Cloud Storage, `calitp-map-tiles` | Public bucket, free to read | ~150 MB of speed maps, cached in Actions and downloaded again only when new | n/a | None |
| data.ca.gov (CKAN: CCRS crashes, Cal-ITP speeds) | No key; no published limit | Not collected yet (roadmap E1) | n/a | Page through large tables politely |
| data.lacity.org (Socrata) | No key needed; anonymous requests are throttled, and a free app token raises the limit (check) | Ad hoc queries only | n/a | Get an app token if a scheduled job starts using it |
| Caltrans GIS (ArcGIS FeatureServer) | Open | One-off snapshot (`fetch_calitp.py`) | n/a | None |
| HERE Traffic API v7, **flow** (`GET data.traffic.hereapi.com/v7/flow?in=bbox:...&locationReferencing=shape&apiKey=...`) | **5,000 transactions a month** for Traffic, one per request (HERE pricing page). Above that €2.20 per 1,000, billed only if a payment method is on the account | 5 boxes × 24 runs a day = **about 3,600 a month** (hourly, from 2026-11-19) | About 28% of the free allowance left | Do not go back to every 30 minutes (7,200 a month). A new street adds a box, or 720 a month; merge nearby streets into one box instead. Key in repository secret `HERE_API_KEY` |
| Telraam | Free API key with a daily call limit (check) | Not used yet (roadmap A10) | n/a | An hourly fetch per segment is small |
| NOAA weather (roadmap E3) | Free; the Climate Data Online API needs a free token, about 10,000 requests a day (check). The Iowa Environmental Mesonet serves ASOS without a key | Not used yet | n/a | Host must be added to the session allowlist |

## How adding a street changes usage

Adding Pico Bl, its control Olympic Bl, and Westwood Bl on 2026-11-19 cost:
- **TomTom**: 8 new zoom-14 tiles (22 to 30), about 23,000 more Vector Flow Tile requests a month.
- **Swiftly, Workers, R2 writes**: nothing. The Swiftly feed already carries every LA Metro bus, and the collector
  stores the whole feed; lines 30, 28, 761 and 233 are picked out later in `pipeline/swiftly_to_pings.py`.
- **R2 reads and the hourly workflow**: nothing extra downloaded; a little more CPU time for two more streets'
  roll-ups.
- **Cal-ITP bucket**: nothing; the same files are re-read.
- **GitHub repository**: about 1 MB of scheduled-speed Parquet per street now, then one small observed CSV and one traffic CSV
  a month.

## Exactly what is called at TomTom

The traffic Worker (`worker/traffic.js`, function `collectTomTom`) makes this request once per tile every 15
minutes, 30 tiles per run:

    GET https://api.tomtom.com/maps/orbis/traffic/flow/vector/tile/14/{x}/{y}?apiVersion=2
        &attributes=tags(absolute_speed,relative_speed,road_category,road_closure,part_of_two_way_road,openlr),roadCategories(primary,secondary,tertiary)
    Header: TomTom-Api-Key: <key>     (Worker secret TOMTOM_API_KEY, from the repository secret)

- **Product**: TomTom Orbis Maps Traffic API, service version 2.
- **Endpoint**: Vector Flow Tiles, zoom 14 (about 2.4 km square at LA's latitude).
- **Response**: Mapbox Vector Tile (protobuf), with one layer, "Traffic flow".
- **Billing**: each tile counts as one request against "Traffic Flow & Incidents API Vector Tiles".

Nothing else at TomTom is called on a schedule. The one-off incident check on 2026-11-18 used the older Traffic API
v5 path `GET https://api.tomtom.com/traffic/services/5/incidentDetails` (Incident Details, billed as "Traffic
Incidents API Details").

For any future street, the TomTom tile count is the only number that grows directly. Check it at
`https://aviary.herebox.org/traffic/status` (`tomtom.of`).

## Where the numbers come from

- TomTom: `docs.tomtom.com/pricing`, read 2026-11-19. `developer.tomtom.com/pricing` now redirects there. Free
  amounts are **monthly** and per product: "Free monthly requests per API, no credit card needed". The rows that
  matter, each tagged for both "TomTom Maps" and "TomTom Orbis Maps":
  - "Traffic Flow & Incidents API Vector Tiles": 200K a month.
  - "Traffic Incidents API Details": 2.5K a month.
  - "Traffic Flow API Segment Data" (not used; tagged "TomTom Maps" only): 20K a month.

  The page gives no price per 1,000 above the free amount. The FAQ asks whether requests fail or are charged at the
  limit, and whether the allowance is per account or per key, but shows no answers. The daily figures quoted
  elsewhere (50,000 tiles and 2,500 other requests a day) are an older scheme and no longer apply. **Owner: in the
  TomTom dashboard, check the usage counter and whether a payment method is attached** (without one, going over
  should fail rather than bill, but the page does not say).
- Swiftly: the limit was given with the key (see `AGENTS.md`, Swiftly section).
- Cloudflare: `developers.cloudflare.com/workers/platform/limits` (cron triggers, requests, CPU) and
  `developers.cloudflare.com/r2/pricing` (storage and operations).
- Usage figures: tile counts from `/traffic/status`; object counts from the collectors' schedules and the
  `aws s3 sync` steps in `.github/workflows/publish.yml`.
