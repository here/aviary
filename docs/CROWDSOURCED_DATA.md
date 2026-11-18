# Crowdsourced traffic data

Started 2026-11-18. Data collected by residents and community groups, rather than by agencies or companies, to
measure streets before and after a redesign. Telraam is the first source explored; others are listed below for
later. Facts here come from the linked pages and web search summaries; verify before quoting.

## Why crowdsourced data matters for this project

- **It covers what official feeds miss.** Bus GPS only measures streets with buses. Fountain Av in West Hollywood
  has no bus service, so its road diet can only be measured with counts taken on the street itself.
- **It measures mode shift.** A road diet is meant to change who uses the street: more people biking and walking,
  slower but steadier cars. Counts by mode show that; vehicle speeds alone do not.
- **It is open by default.** Community counts can be published for anyone to check, which suits a public demo
  built on open standards.
- **It can respect privacy.** The tools below count without identifying people or vehicles. That is the line this
  project draws: anonymous counts yes, licence-plate or face tracking no.

## Telraam (first source)

[Telraam's traffic counter](https://telraam.net/en/our-traffic-counter) is a small camera unit placed inside a
window facing the street. It counts cars, heavy vehicles, bikes and pedestrians separately and measures car speeds.
Counting happens on the device, and no images are stored or sent, so no one can be identified. Counts are published
on Telraam's public map and through its API, by street segment.

### Example: Lake Street, San Francisco

In 2022, residents of Lake Street in San Francisco installed Telraam counters in their windows to document car
volumes and speeds on a street they wanted kept as a "Slow Street". Their counts became part of the public case
for keeping the street calm, as reported by
[Streetsblog San Francisco](https://sf.streetsblog.org/2022/12/19/advocates-used-ai-to-win-slow-lake-fight/).

The same coverage noted that San Francisco's transportation agency said it could not use community-collected data
in its own decisions. The lesson for this project: crowdsourced counts are strongest as a transparent public record
that makes a case visible, alongside official data rather than in place of it.

### Example: a live map of Bay Area counters

[Transpo Maps: Traffic Monitoring](https://transpomaps.org/projects/telraam/) is "a live map of Telraam traffic
monitoring sensors across the San Francisco Bay Area", showing active counters in San Francisco and Berkeley coloured
by average daily vehicle volume, with counts of pedestrians, bikes and vehicles and the speed 85% of vehicles stay
under. It pulls from Telraam's API and is a fiscally sponsored project of the nonprofit Community Streets. It does not
cover Los Angeles, but it shows the kind of public view a set of LA counters could feed.

### Plan for Los Angeles

Site list, data integration and next steps are in [`docs/projects/telraam.md`](projects/telraam.md). In short:

1. Put the first counters on Fountain Av in West Hollywood and on Sunset Bl by the Vista Theatre, before construction
   starts on each (late 2026 to early 2027), so the "before" is recorded.
2. Add a control site on an untouched stretch nearby for each.
3. Pull the hourly counts into the archive next to the bus speeds (`pipeline/fetch_telraam.py`, untested until an
   API key exists).

## OpenTrafficCam (open-source video counting)

[OpenTrafficCam](https://opentrafficcam.org/) is an open-source system for recording street video and analysing it
automatically. It is developed mainly by platomo, a German company, with researchers at TU Dresden, and published
largely under the GNU General Public License v3.0 (code on GitHub: github.com/OpenTrafficCam). Its site is in German.

- **Parts**: OTCamera, a do-it-yourself camera on a Raspberry Pi Zero in a waterproof case that records for up to a
  week on a battery pack; OTVision, which detects and tracks road users in the video to produce their paths
  (trajectories); and OTAnalytics, which turns paths into counts, turning movements and speeds, with a desktop
  interface. OTLabels helps train detection models.
- **What it measures**: counts across a street or through an intersection, by type of road user (7 classes in the
  open-source version, 18 in a paid version), speeds, single-vehicle records, and where people dwell.
- **Where the processing happens**: on a computer after recording, not on the camera. Regular analysis needs a
  powerful machine with a strong graphics card. The company also sells assembled cameras and analysis as a service.
- **Privacy**: the camera is set up so faces and licence plates cannot be identified: low resolution, deliberate
  defocus, mounting more than 3 metres from road users, and masking of irrelevant parts of the picture. The project
  describes this as usable under Europe's data protection rules (GDPR). Unlike Telraam, video is recorded and kept
  until it is analysed, so storage and deletion need a clear policy.

**Compared with Telraam**: OpenTrafficCam gives richer detail (paths, turning movements, any camera angle,
including intersections such as the six-way junction at Hollywood, Sunset and Hillhurst) and is fully open source,
but needs more work: building or buying cameras, mounting them outdoors, handling recorded video, and running
analysis on a capable computer. Telraam is simpler for residents and publishes counts automatically. A practical mix:
Telraam for continuous counts at residents' windows, OpenTrafficCam for short, detailed studies at one intersection
before and after construction, with a written policy for the video.

## Other crowdsourced sources (later)

| Source | What it gives | Access | Notes |
|---|---|---|---|
| Strava Metro | Bike and run trips by street segment, from app users | Free for agencies and approved researchers | Skews toward sport cyclists; roadmap A2 |
| Volunteer bike and pedestrian counts | Manual counts at intersections on set days | Published by local groups when available | Streets For All and the LA County Bicycle Coalition have run counts |
| Resident speed checks | Spot speeds with a radar gun or phone app | Do-it-yourself | Useful for a quick before/after on one block; needs a consistent method |
| Waze user reports | Jams, hazards and closures reported by drivers | Not public; shared with partner agencies through Waze for Cities | Ask LADOT (roadmap A3) |
| MyLA311 requests | Resident reports of street problems by location | Open data on the city portal | Indirect signal of conditions; not traffic counts |
| OpenStreetMap | Street layout, bike lanes, crossings, edited by volunteers | Open | Records what was built and when, for dating each project |

Status of each lives in [`docs/ROADMAP.md`](ROADMAP.md).
