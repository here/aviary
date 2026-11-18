# Telraam counters: exploration notes

Status: exploring (roadmap item A10). Started 2026-11-18. Facts below come from web search summaries on
2026-11-18 unless marked; verify on telraam.net before buying or quoting.

## What it is

Telraam is a small camera unit that sits inside a window facing the street and counts passing road users. It was
developed in Leuven, Belgium, and is aimed at residents and community groups.

- **What it counts**: cars, vans or heavy vehicles, bikes and pedestrians, separately, plus car speed as it passes.
  Counts are published as 15-minute or hourly totals per street segment.
- **Privacy**: counting happens on the device (an AI chip). The camera is deliberately low resolution and the device
  neither stores nor sends images, so individuals and vehicles cannot be identified. This is the main reason it fits
  this project, where plate reading does not.
- **Connection**: the current model (Telraam S2) can use a built-in mobile-data (LTE-M) connection, so it does not
  need the host's Wi-Fi. Older units needed Wi-Fi.
- **Accuracy**: around 85 to 90 percent for cars in published accounts; lower for bikes and pedestrians.
- **Open data**: every unit's counts appear on Telraam's public map and through its API, by segment.
- **To verify**: current S2 price and data subscription in the US; whether it counts at night (earlier models
  counted in daylight only); window height and distance limits.

Sources: [TechCrunch on San Francisco sensors](https://techcrunch.com/?p=2543774),
[Traffic Technology Today on the S2](https://www.traffictechnologytoday.com/news/traffic-counting-categorization/telraam-launches-new-ai-traffic-counting-device.html),
[Streetsblog on Lake Street, San Francisco](https://sf.streetsblog.org/2022/12/19/advocates-used-ai-to-win-slow-lake-fight/),
[Kapernikov on the technology](https://kapernikov.com/?p=73851),
[Telraam API collection on Postman](https://documenter.gw.postman.com/view/metadata/TWDRqyaV),
[telraamR package](https://juanfonsecals1.github.io/telraamR/reference/read_Telraam_traffic.html).

## Prior use in the US

- **San Francisco, 2022 to 2023**: Lake Street residents bought units to show car volumes and speeds; about 50 were
  installed across the city by May 2023. San Francisco's transportation agency said it could not use
  community-collected data in its decisions. Lesson: the value here is a public, transparent record for the
  demo and for advocacy, not data an agency will adopt as-is.
- **Los Angeles**: no deployments found by search. Check Telraam's live map for any existing segments near the
  study streets before buying; an existing unit gives history for free.

## Why it fits this project

- **Fountain Av has no bus data in West Hollywood**, so the bus method cannot measure the road diet there.
  Telraam can count cars and bikes and give car speeds before and after the lane reduction.
- **Lyman Pl to Fountain Av** (Hollywood project Phase 2, early 2027): bus GPS covers line 2, but not general
  traffic, bikes or pedestrians. A unit overlooking Sunset near the Vista Theatre would add those.
- **Mode shift is the story a road diet is meant to tell**: more bikes and pedestrians, slower but steady cars.
  Bus GPS alone cannot show it.

## Candidate sites (need a willing host with a street-facing window)

| Priority | Location | Treated or control | Timing |
|---|---|---|---|
| 1 | Fountain Av, West Hollywood (between La Cienega Bl and La Brea Av) | Treated (road diet, construction expected late 2026 / early 2027) | Install as soon as possible to capture "before" |
| 2 | Sunset Bl between Hillhurst Av and Fountain Av (by the Vista Theatre) | Treated (Hollywood Phase 2, early 2027) | Same |
| 3 | Fountain Av in Hollywood (east of La Brea Av, not part of the WeHo project) | Control for site 1 | Same time as site 1 |
| 4 | Hollywood Bl between Gower St and Hillhurst Av | Treated (Phase 1, built 2024): "after" only | Any time |
| 5 | Hollywood Bl west of Gower St | Control for site 4 | Any time |

Possible hosts and partners (owner to approach): residents and businesses on each street, Hollywood United and
East Hollywood neighborhood councils, West Hollywood residents' groups, Streets For All, Los Angeles Walks.

## How the data would join the archive

1. Each unit belongs to a Telraam road segment with a numeric id. Record the ids in the street's
   `corridors/<id>.json` as `"telraam_segments": [{"id": ..., "section_id": "S2", "label": "..."}]`.
2. `pipeline/fetch_telraam.py` (written 2026-11-18, **untested until a key exists**) pulls hourly counts for those
   segments into `data/corridors/<id>/telraam/<id>_telraam_YYYY-MM.csv`, one file per month, merged like the
   observed speeds. Columns: hour, segment, uptime, counts by mode, car speed percentile (v85).
3. The hourly workflow runs it; `build_datapackage.py` then lists the files; the page can add a counts panel.
4. API access: a free Telraam account gives an API key (basic hourly data); 15-minute data needs the paid
   "Advanced" tier. The key is sent in a request header, so this session can store it with the secure form,
   and the workflow needs it as a repository secret `TELRAAM_API_KEY`.

## Owner's next steps

1. Look at Telraam's map (telraam.net) for any existing units near the study streets.
2. Check the current S2 price, data subscription and US shipping; order one or two for sites 1 and 2.
3. Create a free Telraam account and API key.
4. Line up hosts for the first sites.
