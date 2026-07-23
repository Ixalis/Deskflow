# DeskFlow

DeskFlow is a small coworking operations platform built to explore three problems that look simple until real constraints arrive: preventing overlapping reservations, pricing inventory from occupancy, and reporting revenue in the operator's local day.

The project uses FastAPI, SQLAlchemy, SQLite, TypeScript and Vite. It began as a backend exercise and grew into a test bed for timezone handling, booking concurrency and database portability.

## What it does

- Creates bookable spaces with capacity, hourly price in integer VND and an IANA timezone.
- Produces quotes with occupancy tiers and a local-weekend discount.
- Rejects overlapping confirmed bookings while allowing exact back-to-back boundaries.
- Cancels bookings and releases their time interval.
- Reports booked hours and prorated revenue for a requested local calendar day.
- Serves a small TypeScript interface from a separate Vite development server.

## Design choices

### UTC storage, local business rules

API timestamps must include an offset. They are normalized to UTC before persistence because SQLite does not reliably preserve timezone information. Weekend pricing and daily analytics are converted back through the workspace or requested IANA timezone.

### Integer VND

Prices are stored as integer Vietnamese dong. This avoids binary floating-point drift and matches a currency with no commonly used fractional unit.

### Booking serialization

Booking creation locks the parent space row before checking for overlap. PostgreSQL honors the `SELECT ... FOR UPDATE` lock and serializes competing requests for the same space. SQLite ignores row-level locks but serializes writes for the local MVP. A PostgreSQL exclusion constraint would be the next defense-in-depth step.

### Portable analytics

Booked hours are calculated in Python from intervals returned by standard SQL comparisons. The first implementation used SQLite's `julianday`, which made a future PostgreSQL migration deceptively impossible.

## Run locally

### API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The OpenAPI interface is available at `http://127.0.0.1:8000/docs`.

### Web interface

```bash
cd frontend
npm install
npm run dev
```

The API allows `http://localhost:5173` and `http://127.0.0.1:5173` by default. Override the comma-separated `ALLOWED_ORIGINS` environment variable for other environments.

### Tests

```bash
pytest -q
```

The suite covers timezone normalization, CORS, boundary-safe bookings, overlap rejection, weekend and occupancy pricing, cancellation, validation and local-day analytics.

## API sketch

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/spaces` | Create a workspace |
| `GET` | `/spaces` | List active workspaces |
| `POST` | `/quotes` | Calculate a price quote |
| `POST` | `/bookings` | Create a confirmed booking |
| `PATCH` | `/bookings/{id}/cancel` | Cancel a booking |
| `GET` | `/analytics/daily` | Report a local calendar day |

Example space:

```json
{
  "name": "Focus Room",
  "capacity": 4,
  "base_hourly_rate_vnd": 100000,
  "timezone_name": "Asia/Ho_Chi_Minh"
}
```

Example quote interval:

```json
{
  "space_id": 1,
  "start_time": "2026-07-25T09:00:00+07:00",
  "end_time": "2026-07-25T11:00:00+07:00"
}
```

## Repository map

```text
app/                 FastAPI routes, schemas, models and services
frontend/            TypeScript/Vite client
tests/               API and domain regression tests
docs/                Architecture, product notes and postmortems
.github/workflows/    Continuous test workflow
```

## Current limits

- The default database is SQLite for a zero-setup local run.
- The pricing rules are deliberately simple and not yet configurable per operator.
- Availability is checked through the application path; a PostgreSQL range exclusion constraint would provide stronger database-level protection.
- Authentication, payment and multi-tenant access control are outside this MVP.

## Live demo

[Open DeskFlow](https://deskflow-web-seven.vercel.app)
