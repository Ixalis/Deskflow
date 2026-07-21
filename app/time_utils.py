from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def validate_timezone_name(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone: {value}") from exc
    return value


def to_utc_naive(value: datetime) -> datetime:
    """Normalize an offset-aware datetime to naive UTC for portable storage.

    SQLite does not preserve timezone offsets reliably. Keeping every persisted
    timestamp in one canonical representation makes overlap comparisons stable
    across SQLite and PostgreSQL.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset")
    return value.astimezone(UTC).replace(tzinfo=None)


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def local_day_utc_bounds(day: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(validate_timezone_name(timezone_name))
    local_start = datetime.combine(day, time.min, tzinfo=zone)
    next_day = date.fromordinal(day.toordinal() + 1)
    local_end = datetime.combine(next_day, time.min, tzinfo=zone)
    return (
        local_start.astimezone(UTC).replace(tzinfo=None),
        local_end.astimezone(UTC).replace(tzinfo=None),
    )


def as_local(value_utc_naive: datetime, timezone_name: str) -> datetime:
    zone = ZoneInfo(validate_timezone_name(timezone_name))
    return value_utc_naive.replace(tzinfo=UTC).astimezone(zone)
