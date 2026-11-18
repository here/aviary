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
