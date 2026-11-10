# Data source loading and provenance

This document separates live provider behavior from fixture-only tests. Unit tests never
call Google or MTA endpoints. Live smoke tests must be bounded, redacted, and opt-in.

## MTA Subway Stations — Ruochen

- Dataset: New York State Open Data, MTA Subway Stations (`39hk-dx4f`).
- Human-readable page:
  `https://data.ny.gov/Transportation/MTA-Subway-Stations/39hk-dx4f/about_data`
- Socrata JSON endpoint: `https://data.ny.gov/resource/39hk-dx4f.json`
- Bounded request: `$limit=5000`, JSON accept header, 15-second timeout, no credential.
- Consumed fields: `station_id`, `gtfs_stop_id`, `complex_id`, `stop_name`, `borough`,
  `daytime_routes`, `gtfs_latitude`, and `gtfs_longitude`.
- Stable candidate ID: `area:mta:<station_id>`.
- Provenance: each selected station receives its own `Source` with dataset ID, station
  ID, retrieval timestamp, provider record ID, page URL, and attribution.

`commonground/research/expansion.py` owns parsing, validation, duplicate removal,
selection, and ResearchResult normalization. The selector excludes name matches and
stations within 0.5 km of initial candidates, prefers bounded group-distance and route
diversity, and emits at most three expansion candidates. These heuristics only propose
areas; Routes and Places must still verify feasibility.

For Cloud Run, load one snapshot at process startup and retain it in memory for that
instance. A fetch failure should surface as explicit missing evidence rather than reuse
an unversioned stale response. If a committed/GCS cache is added later, store the raw
JSON with retrieval timestamp and dataset ID; never overwrite it without recording the
refresh time. The current repository intentionally does not commit a live snapshot.

## Google Routes — Andrew

The existing Project 1 Routes request layer remains authoritative. Project 2's Transit
adapter will normalize area-center and exact-cafe responses into facts, sources, and
gaps while preserving arrival time and per-traveler identity. API credentials stay in
the server environment and never enter source records or traces.

## Google Places — Wenyu/Yulia

The existing Project 1 Places and opening-hours layers remain authoritative. Project 2's
`run_cafe_task` reuses the request boundary and normalizes identity, exact address and
coordinates, rating, price, business status, and meeting-time hours. Future regular
hours are provisional; missing fields remain explicit gaps. All matched parent area
IDs survive deduplication. API credentials stay in the server environment.

The opt-in one-area live check is `python -m evals.yulia_delivery places-smoke --live`
with a future `--meeting-time`. It records citations, unknown hours, request bounds,
and whether real provider data was obtained. The current committed capture is
**blocked**, because no Maps key is configured. It is not a live Places observation.
See `YULIA_ACCEPTANCE.md` for commands and the separate frozen-model capture gate.
