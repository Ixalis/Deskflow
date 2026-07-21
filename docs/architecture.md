# Architecture notes

The backend uses FastAPI, Pydantic and SQLAlchemy with a small layered split:

- API routes validate inputs and translate domain exceptions into HTTP responses.
- Schemas normalize timezone-aware inputs to UTC before persistence.
- Services contain pricing, conflict detection, booking, cancellation and analytics logic.
- Models represent persisted relational data.

## Time model

Persisted timestamps use naive UTC for consistent comparison in SQLite and PostgreSQL. Each workspace stores an IANA timezone for local pricing rules. Daily analytics accepts an explicit IANA timezone because a calendar day is not globally unique.

## Concurrency model

Booking creation locks the parent workspace row with `SELECT ... FOR UPDATE`, checks for overlap and inserts within one transaction. PostgreSQL therefore serializes booking attempts for the same workspace. SQLite ignores the row-lock clause but serializes writes in the local MVP.

A production PostgreSQL deployment should additionally use a range exclusion constraint on confirmed bookings so correctness is not dependent on every future code path remembering the service lock.

## Database portability

The original occupancy query used SQLite's `julianday`. The current version selects overlapping intervals using portable SQL and calculates clipped durations in Python. Money is represented as integer VND rather than floating point.
