# Postmortem: timezone offsets caused false booking conflicts

## Summary

DeskFlow originally accepted ISO timestamps with offsets but stored and compared them without first converting them to one canonical timezone. A booking submitted in `+07:00` could therefore conflict with a later booking submitted in `+00:00`, even when the two represented different real-world intervals.

The failure was not in the overlap formula. The interval condition itself was correct:

```text
existing.start < requested.end AND existing.end > requested.start
```

The problem was that the values reaching that comparison did not share the same frame of reference.

## User impact

A customer could receive HTTP 409, "space is already booked," for an interval that was actually available. The bug was especially likely when a browser, API client and database server used different timezone conventions.

## Reproduction

1. Create a booking for `2026-07-21 09:00-10:00 +07:00`.
2. Request another booking for `2026-07-21 03:30-04:30 +00:00`.
3. The second interval is `10:30-11:30 +07:00`, so it should be accepted.
4. The original implementation could return 409 because SQLite compared serialized timestamps without reliable offset semantics.

## Root cause

Three assumptions combined badly:

- Pydantic parsed offset-aware timestamps correctly.
- SQLAlchemy's SQLite `DateTime` column did not preserve those offsets as a portable instant.
- The service trusted database comparison without normalizing the values first.

The API therefore looked timezone-aware at its boundary while behaving timezone-naive internally.

## Fix

- Require every booking timestamp to include an explicit offset.
- Convert accepted timestamps to UTC before database access.
- Store timestamps as naive UTC in both SQLite and PostgreSQL-compatible models.
- Store an IANA timezone on each workspace for business rules.
- Convert UTC timestamps into that zone for weekend pricing.
- Accept an IANA timezone for daily analytics and calculate its UTC day boundaries.
- Replace deprecated `datetime.utcnow()` with an explicit UTC clock helper.

## Verification

Regression tests now cover:

- Equivalent and non-equivalent intervals submitted with different offsets.
- Rejection of timestamps without offsets.
- A Saturday discount evaluated in `Asia/Ho_Chi_Minh`, even when the UTC date differs.
- Analytics for a booking that crosses local midnight.

## What I rejected

### Store whatever offset the client sent

This preserves presentation context but makes equality and overlap reasoning dependent on database behavior. It also allows equivalent instants to have different stored forms.

### Treat naive timestamps as server-local time

That silently changes meaning when the API moves between machines or containers. Rejecting ambiguity is safer than guessing.

### Apply all business rules in UTC

Storage should use UTC, but coworking operators sell local clock time. A Saturday discount belongs to the workspace's Saturday, not the server's.

## Follow-up work

- Return timestamps with an explicit `Z` suffix or workspace-local representation instead of naive-looking response strings.
- Add PostgreSQL integration tests around concurrent booking creation.
- Add workspace opening hours and validate bookings against local wall-clock availability.
- Decide how daylight-saving transitions should behave for spaces outside Vietnam.
