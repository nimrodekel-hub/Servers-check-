---
name: elevator-map
description: Build, extend, and connect the elevator-inspection map feature (elevator-map.html) that shows required elevator inspections on a Leaflet/OpenStreetMap map with date-range filtering. Use when working on the map view, geocoding customer addresses to coordinates, wiring the map to the .NET/SQL backend as a JSON feed, or adding filters, clustering, and navigation links.
---

# Elevator Inspections Map

A map view for the elevator customer/inspection management system. It plots
required inspections on a map and filters them by date range (e.g. "next
week"). Front-end lives in `elevator-map.html`; it is a self-contained page
using **Leaflet + OpenStreetMap** (no API key, free) and **Leaflet.markercluster**.

## Architecture

```
SQL (customers + inspections + addresses)
        │
        ├─ one-time Geocoding (address → Lat/Lng, cached in DB columns)
        ▼
   .NET endpoint  ──►  GET /api/inspections?from=YYYY-MM-DD&to=YYYY-MM-DD  →  JSON
        ▼
   elevator-map.html (Leaflet)  ──►  markers + date filter + side list
```

The front-end is backend-agnostic: it only needs a JSON array. Any .NET stack
(ASP.NET MVC/Razor, Blazor, or Web API + separate front-end) can serve it.

## JSON contract

The map expects an array of inspection objects. Keep these exact field names
(the front-end reads them directly):

```json
[
  {
    "id": 3,
    "customer": "קניון עזריאלי",
    "address": "דרך מנחם בגין 132, תל אביב",
    "lat": 32.0742,
    "lng": 34.7920,
    "date": "2026-07-21",
    "inspector": "אבי כהן",
    "status": "מתוזמנת"
  }
]
```

- `date` is ISO `YYYY-MM-DD`.
- `lat`/`lng` are decimal degrees. Rows without coordinates should be skipped
  or geocoded first (see below).

## Connecting the front-end to the real endpoint

In `elevator-map.html`, the sample array `INSPECTIONS` is the only thing to
replace. Swap the hard-coded array for a fetch. Recommended pattern — fetch on
each range change so the server does the date filtering:

```js
async function loadInspections(r) {
  const qs = r.start
    ? `?from=${r.start.toISOString().slice(0,10)}&to=${r.end.toISOString().slice(0,10)}`
    : "";
  const res = await fetch(`/api/inspections${qs}`);
  return res.json();
}
```

Then make `render()` async: `const rows = await loadInspections(current);`
(drop the local `.filter(inRange)` once the server filters by date).

For a first integration it is also fine to fetch the full list once and keep
the existing client-side `inRange` filtering.

## Geocoding (addresses → coordinates)

The source data has **text addresses only**, so coordinates must be produced
once and cached. Add `Lat`/`Lng` (nullable `float`/`decimal`) columns to the
customer/site table and backfill them.

Use **Nominatim** (OpenStreetMap's free geocoder). Usage policy matters:

- **Max 1 request/second.** Batch as a background/one-time job, not per page load.
- Send a real `User-Agent` identifying the app.
- **Cache the result in SQL** — never geocode the same address twice.
- Bias to Israel with `countrycodes=il`.

Minimal C# geocoder (run once per address, store the result):

```csharp
public record GeoResult(double Lat, double Lng);

public async Task<GeoResult?> GeocodeAsync(string address, HttpClient http)
{
    var url = $"https://nominatim.openstreetmap.org/search" +
              $"?q={Uri.EscapeDataString(address)}&format=json&limit=1&countrycodes=il";
    var req = new HttpRequestMessage(HttpMethod.Get, url);
    req.Headers.UserAgent.ParseAdd("ElevatorInspections/1.0 (contact@omnisys.co.il)");
    var arr = await http.GetFromJsonAsync<List<Dictionary<string, object>>>(url);
    var first = arr?.FirstOrDefault();
    if (first is null) return null;
    return new GeoResult(
        double.Parse(first["lat"].ToString()!, CultureInfo.InvariantCulture),
        double.Parse(first["lon"].ToString()!, CultureInfo.InvariantCulture));
    // remember to Task.Delay(1100) between calls, and persist Lat/Lng to SQL
}
```

For higher accuracy/volume in Israel, Google Geocoding is an alternative but
requires an API key and billing.

## Front-end conventions (elevator-map.html)

- **RTL Hebrew**, styled to match `index.html` (same CSS variables / blue
  gradient header).
- **Marker color = urgency**, computed from days until the inspection date:
  - overdue (`< 0`) → red `#dc2626`
  - within 7 days → orange `#d97706`
  - within 30 days → blue `#2563eb`
  - later → green `#16a34a`
  - Keep `urgency()` and the legend in sync if you change thresholds.
- **Date ranges** live in `rangeFor(kind)`: `today`, `week`, `nextweek`,
  `month`, `all`, plus a custom from/to picker. Week starts Sunday (`getDay()`
  `0` = Sunday) per the Israeli week.
- **Clustering** via `L.markerClusterGroup()` — keep it; the real dataset will
  have many points. Use `cluster.zoomToShowLayer(m, …)` before opening a popup.
- **Navigation links** in each popup: Google Maps directions + Waze deep link.
- Side list stays synced with the map; clicking an item pans/zooms to its marker.

## Ideas / backlog

- Server-side date filtering (move `inRange` to SQL `WHERE`).
- Filter by inspector, status, or region; color/group by inspector.
- "Assign to me" / mark inspection done from the popup (write-back endpoint).
- Route optimization for a day's inspections.
- Auto-geocode new customers on save (with the 1 req/s cache rule).
