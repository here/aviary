# Free tiers and usage

What each service allows without paying, what this project uses, and how much headroom is left. Written
2026-11-19 after adding Pico Bl. **Re-check this file whenever a collector, tile box, polling interval or street is
added**, because those are what move the numbers.

Limits marked "check" come from search summaries or memory and have not been confirmed on the provider's own page.
Confirm them in the provider's dashboard before relying on them.

## Summary

| Service | Free allowance | This project uses | Headroom | Watch |
|---|---|---|---|---|
| TomTom (traffic flow tiles) | 50,000 tile requests and 2,500 non-tile requests **a day** (TomTom developer store; the docs pricing page lists *monthly* figures, so check) | 26 tiles × 96 runs = **2,496 tile requests a day** | About 20× on the daily figure | Each new street adds 1 to 4 zoom-14 tiles (~100 to 400 a day). Incidents (roadmap E2) would add 96 non-tile requests a day |
| Swiftly (LA Metro realtime) | 180 requests per 15 minutes per key | Vehicle positions every minute plus trip updates every 15 minutes = **16 per 15 minutes** | About 11× | Requests are not per street, so adding Pico costs nothing. Ask Swiftly about storage and redistribution terms |
| LA Metro websocket | No key, no published limit | One connection a minute (lines 204, 754, 2, 4) | n/a | Line 30 (Pico) comes from Swiftly only |
| Cloudflare Workers (free plan) | 100,000 requests a day; 5 cron triggers per account; 10 ms CPU per invocation (check) | 3 cron Workers: collector every minute, GBFS every 10 minutes, traffic every 15 minutes = **~1,680 runs a day**, plus page and API visits | Wide on requests; **2 cron triggers left** | CPU per run is the tight limit (gzipping a minute of messages). A new collector should share an existing cron rather than add a fourth or fifth |
| Cloudflare R2 storage | 10 GB stored; 1 million Class A (writes, lists) and 10 million Class B (reads) operations a month; no egress fees (check on Cloudflare's pricing page) | Storage grows ~3.5 GB a month, almost all Swiftly snapshots (`swiftly/`, no expiry). Writes ~5,000 a day (~150,000 a month). Reads: the hourly workflow re-downloads two days of minute files each run, **~6,000 objects an hour, ~4.3 million a month** | Storage runs out around **February 2027** (roadmap B2). Reads at ~43% of the free allowance | Reads double if the workflow window grows to four days. To cut them, cache downloads between runs or fetch only new hours |
| GitHub Actions and Pages | Public repository: standard runners free with no minute cap; Pages free | Hourly publish run (~5 to 10 minutes), weekly Cal-ITP refresh | n/a | Scheduled runs are sometimes dropped (roadmap D1). Keep data commits small: the repository grows with every monthly CSV |
| Google Cloud Storage, `calitp-map-tiles` | Public bucket, free to read | ~150 MB of speed maps, cached in Actions and downloaded again only when new | n/a | None |
| data.ca.gov (CKAN: CCRS crashes, Cal-ITP speeds) | No key; no published limit | Not collected yet (roadmap E1) | n/a | Page through large tables politely |
| data.lacity.org (Socrata) | No key needed; anonymous requests are throttled, and a free app token raises the limit (check) | Ad hoc queries only | n/a | Get an app token if a scheduled job starts using it |
| Caltrans GIS (ArcGIS FeatureServer) | Open | One-off snapshot (`fetch_calitp.py`) | n/a | None |
| HERE Traffic API v7 | Free "Base" or limited plan with a monthly transaction allowance (check) | Built but idle (no key). It would use 4 boxes × 48 runs a day = **~5,800 requests a month** | Unknown until a plan is chosen | Only turn it on after confirming the allowance |
| Telraam | Free API key with a daily call limit (check) | Not used yet (roadmap A10) | n/a | An hourly fetch per segment is small |
| NOAA weather (roadmap E3) | Free; the Climate Data Online API needs a free token, about 10,000 requests a day (check). The Iowa Environmental Mesonet serves ASOS without a key | Not used yet | n/a | Host must be added to the session allowlist |

## How adding a street changes usage

Adding Pico Bl and its control, Olympic Bl, on 2026-11-19 cost:
- **TomTom**: 4 new zoom-14 tiles (22 to 26), about 380 more tile requests a day.
- **Swiftly, Workers, R2 writes**: nothing. The Swiftly feed already carries every LA Metro bus, and the collector
  stores the whole feed; lines 30 and 28 are picked out later in `pipeline/swiftly_to_pings.py`.
- **R2 reads and the hourly workflow**: nothing extra downloaded; a little more CPU time for two more streets'
  roll-ups.
- **Cal-ITP bucket**: nothing; the same files are re-read.
- **GitHub repository**: about 1 MB of scheduled-speed Parquet per street now, then one small observed CSV and one traffic CSV
  a month.

For any future street, the TomTom tile count is the only number that grows directly. Check it at
`https://aviary.herebox.org/traffic/status` (`tomtom.of`).

## Where the numbers come from

- TomTom: the developer store and FAQ (`developer.tomtom.com/store/maps-api`, `developer.tomtom.com/platform/documentation/faqs`)
  state daily free amounts. `docs.tomtom.com/pricing` shows monthly amounts for some APIs. **Owner: confirm in the
  TomTom dashboard which applies to this key, and whether overage is blocked or billed.**
- Swiftly: the limit was given with the key (see `AGENTS.md`, Swiftly section).
- Cloudflare: `developers.cloudflare.com/workers/platform/limits` (cron triggers, requests, CPU) and
  `developers.cloudflare.com/r2/pricing` (storage and operations).
- Usage figures: tile counts from `/traffic/status`; object counts from the collectors' schedules and the
  `aws s3 sync` steps in `.github/workflows/publish.yml`.
