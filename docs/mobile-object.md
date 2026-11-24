# Mobile objects: feeds, standards and a storage strategy

A **mobile object** here is anything that moves through the city and can be located over time: a person walking, a
bus, a train, a car, a ride-hail vehicle, a bike or scooter, a sidewalk delivery robot, a boat. This note compares the
feeds this project already reads (GTFS, GBFS, and the TomTom and HERE traffic data) with GOFS, then asks whether an
open standard exists for storing **one traveller's path** across several modes: positions at an interval, with mode,
street or railway, measured speed, origin, destination and time of day.

Written 2026-11-24 from what the project collects and from memory of the specifications. Items marked "check" have
not been confirmed against the specification text in this session; verify them before quoting.

## 1. What each feed describes

Each feed answers a different question, and only some of them describe moving objects at all.

| Feed | Steward | Question it answers | Unit of record | Moving objects? | History | Used here |
|---|---|---|---|---|---|---|
| **GTFS Schedule** | MobilityData (community spec) | What service is planned? | Route, trip, stop time, shape | No: a plan, not a movement | Each published version; this project rebuilt 2016 onward from LA Metro's git history | Scheduled speed series |
| **GTFS Realtime** (vehicle positions, trip updates, alerts) | MobilityData | Where is each vehicle now, and how late is each trip? | Vehicle position: vehicle id, trip id, route, lat/lon, bearing, speed (optional), timestamp | **Yes**, transit vehicles only | None: snapshots, so you keep what you record | Metro websocket and Swiftly, every minute; measured bus speeds |
| **GBFS** (General Bikeshare Feed Specification) | MobilityData (NABSA before) | What shared vehicles and docks are available now? | Station status; vehicle status (`free_bike_status` before v3) with lat/lon, type, range | Parked vehicles only. Vehicle ids **must rotate after each trip** (since v2.0, check), so trips cannot be followed on purpose | None | `worker/gbfs.js` every 10 minutes into `gbfs/` |
| **GOFS** (General On-demand Feed Specification) | MobilityData (check: v1 adopted around 2022 to 2023) | What on-demand service exists: zones, operating hours, booking rules, fares, typical wait and travel times? | Service zones, calendars, wait-time estimates | No: describes the service offer (like GTFS does for fixed routes), not vehicles or trips. Close to GTFS-Flex | n/a | Not used. Relevant if LA Metro Micro or DASH on-demand is added |
| **MDS** (Mobility Data Specification, began at LADOT) | Open Mobility Foundation | What did each regulated vehicle do? (operator to city) | Trips (origin, destination, route), telemetry points, vehicle events and status | **Yes**, per vehicle. MDS 2.0 covers micromobility, car share, passenger services (taxi, ride-hail) and **delivery robots** (check the exact mode names) | Kept by the city; access restricted | Our bus pings are published in MDS 2.0 telemetry shape (`provider_id` placeholder) |
| **TomTom flow tiles** | TomTom (proprietary) | How fast is traffic on each road piece now? | Road segment: absolute and relative speed, closure, OpenLR reference | **No**: an aggregate of many probe vehicles. No ids, no individual paths | None from the free API; historical products are paid | `traffic/tomtom/` every 15 minutes |
| **HERE Traffic v7 flow** | HERE (proprietary) | Same, along a corridor | Segment: speed, free-flow speed, jam factor, confidence, shape | **No**: aggregate | None from the free API | `traffic/here/` every 90 minutes |
| **TomTom incidents** | TomTom | What is blocking traffic now? | Incident: type, delay, extent, from and to | No: events on the road | None | `traffic/incidents/` every 20 minutes |

### The main difference

- **GTFS, GOFS and GBFS describe what can be used**: planned service, on-demand service and available vehicles. They
  are open, public, and have no history built in. GTFS Realtime is the only one that follows moving objects, and only
  transit vehicles.
- **TomTom and HERE describe how the road performs**: speed per road segment, built from many anonymous probes. The
  individual paths behind them are not available to customers. Their location referencing (OpenLR, TPEG, DATEX II
  for the European equivalents) is the useful open part. It lets you say "this stretch of road" without a shared map.
- **MDS** is the only one of these built around individual vehicle trips and paths. It is a regulatory feed from
  operators to cities, not a public feed and not about riders.

So none of them records a **person's** journey across modes. They record vehicles, services or road segments. A
rider who walks, takes the 204, changes to the B Line and then rides a scooter shows up as fragments: one
anonymous GTFS-RT vehicle, nothing on the rail line from this project, and a GBFS vehicle whose id rotates.

## 2. Open standards for individual paths

No single open standard covers "one traveller, many modes, positions over time, with network references and trip
context". The pieces exist:

| Standard | What it covers | Good for | Missing |
|---|---|---|---|
| **OGC Moving Features** (ISO 19141 model; encodings in XML, Simple CSV, and **MF-JSON**, a GeoJSON extension; plus **OGC API – Moving Features**, check its status) | Any moving object: a trajectory as positions with times, plus time-varying properties (speed, mode, battery, occupancy) on the same timeline | **The closest general fit.** Object type is free; properties like `mode` and `speed` can change along the path. MobilityDB implements the same model | No transport vocabulary: mode, trip, stop and road references are your own. No privacy rules |
| **MDS 2.0 Trips + Telemetry** | One vehicle's trip: start and end, route, telemetry points (lat, lon, speed, heading, accuracy) | Vehicles, including delivery robots and ride-hail; already this project's telemetry shape | One vehicle per trip, not one person. No walking, rail or boats |
| **GPX** | Tracks of points with time and elevation | Simple, readable by almost every tool, common from phones and bike computers | No mode or speed fields without extensions; one person's raw track only |
| **GeoJSON / GeoParquet** | Features and geometry; a LineString plus a parallel list of times is a common convention | Storage and publishing; GeoParquet suits large point tables | Times are a convention, not standard (MF-JSON fixes this) |
| **OGC SensorThings API** | Things, their locations over time, and observations from sensors | Fixed and moving sensors, for example a Telraam counter or a phone | Heavier than needed for paths |
| **Transmodel / NeTEx / SIRI** (CEN, Europe) | Full public-transport data model; SIRI covers live vehicle and journey monitoring | Formal multimodal vocabulary: modes, journeys, legs, interchanges | Built for operators and services, not personal tracks |
| **OJP** (Open Journey Planner, CEN) and **TOMP-API** (Transport Operator to MaaS Provider) | Planned and booked journeys as **legs** with modes, from origin to destination; TOMP adds booking and executed legs (check) | The best existing vocabulary for a **multimodal trip as legs** | Plans and bookings, not measured positions |
| **AIS** (ships, ITU-R M.1371) and **ADS-B** (aircraft) | Live position reports from the vessel or aircraft itself | Boats on the LA and Long Beach harbours, ferries | Their own domains; tie in by mode, not schema |
| **OpenLR**, **SharedStreets references**, OSM way ids, GTFS `shape_id` with distance along it | Saying which street or railway a point is on without sharing a map | The "street / railway" column | Need map-matching first |

### Recommended combination

Use the **OGC Moving Features model** for positions over time, the **OJP / Transmodel idea of legs** for
journeys, and **MDS 2.0 telemetry fields** for the per-point columns. Each journey breaks into legs, each leg has one
mode, and each point belongs to a leg.

## 3. A storage design for this project

Three tables, stored as GeoParquet (yearly) and CSV (monthly), as the rest of the archive is, and described in
`datapackage.json`. MF-JSON is offered as an export for single objects.

**`objects`**: one row per mobile object over its lifetime (or per rotation period of a pseudonymous id).

| Column | Meaning |
|---|---|
| `object_id` | Pseudonymous id; rotated (daily at most for people) |
| `object_class` | `person`, `bus`, `rail_vehicle`, `car`, `ride_hail`, `bicycle`, `scooter`, `delivery_robot`, `boat`, `other` |
| `source` | `gtfs_rt_metro`, `swiftly`, `mds`, `gbfs`, `ais`, `phone_app`, `survey` |
| `operator` | Agency or company, where known |

**`legs`**: one row per continuous movement in one mode.

| Column | Meaning |
|---|---|
| `leg_id`, `journey_id`, `object_id` | A journey is one origin-to-destination trip and holds one or more legs |
| `mode` | `walk`, `wheelchair`, `bicycle`, `scooter`, `bus`, `rail`, `car`, `ride_hail`, `robot`, `ferry` (OJP / GTFS route types where they fit) |
| `vehicle_ref`, `trip_ref`, `route_ref` | The GTFS trip and route, an MDS vehicle, or empty for walking |
| `start_time`, `end_time` (UTC, plus local `time_of_day` band) | |
| `origin`, `destination` | Coarsened: a stop id, a census block group, or a 250 m grid cell. **Never the exact home or work point** |
| `distance_m`, `duration_s`, `mean_speed_mps` | |

**`positions`**: one row per point.

| Column | Meaning |
|---|---|
| `leg_id`, `t` (UTC) | |
| `lat`, `lon`, `accuracy_m` | |
| `speed_mps` (measured, or derived and flagged), `heading_deg` | |
| `network` and `network_ref` | `osm_way`, `openlr`, `gtfs_shape` (with distance along it), or `rail_line` |
| `section` | This project's corridor section, when the point is on a study street |

Queries that span modes and time (for example "every leg through Sunset and Hyperion between 5 and 7 pm") run well in
**MobilityDB** (PostgreSQL with temporal point types), or in DuckDB over the GeoParquet files.

### How this project's existing data fits

| Data | Fits as |
|---|---|
| Metro and Swiftly bus pings | `positions` for `object_class = bus`, with legs per GTFS trip. Already close: they are published in MDS telemetry form |
| GBFS snapshots | Parked-vehicle counts only. Rotating ids stop legs being rebuilt; that is a privacy feature, not a bug |
| TomTom and HERE flow | Not mobile objects. They stay as per-section speeds and serve as the general-traffic comparison for any object's legs |
| TomTom incidents | Events on sections, joined to legs by place and time |
| Telraam (A10) | Counts and car speeds at one point; a fixed sensor, not a path |

## 4. Privacy

Individual paths are personal data even without names. A few points with times are usually enough to identify a
person (de Montjoye et al., 2013, *Unique in the Crowd*: four points identified 95% of people in a phone dataset).
California's CCPA treats precise geolocation as sensitive personal information (check the current wording).

- Collect people's paths only with consent, from volunteers, and say how long they are kept.
- Publish legs and section summaries, not raw points. Coarsen origin and destination, cut the first and last few
  hundred metres of each journey, and rotate object ids.
- Publish only counts that cover several people (for example at least 5 per cell and hour).
- Vehicles in service (buses, robots, ride-hail between trips) carry less risk than people, but MDS practice still
  treats trip data as sensitive. The OMF has published guidance on this (check its current location).

## 5. Possible next steps

Not on the roadmap yet; add an item if the owner wants one.

1. Convert the bus pings into the `legs` and `positions` tables, with an MF-JSON export of one bus trip for the
   talk. This uses only data already collected.
2. A small volunteer test: a few people record a multimodal trip along a study street with a GPX or OpenTracks app,
   label the modes, and the trip is stored with the rules above.
3. Ask LADOT (A3) whether MDS delivery-robot and scooter trips on the study streets can be shared in aggregate.
4. If boats are wanted, the San Pedro Bay ports have public AIS coverage. That is off the study streets and a
   separate project.
