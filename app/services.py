from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Booking, Space
from .time_utils import as_local, local_day_utc_bounds, validate_timezone_name


class BookingConflictError(ValueError):
    pass


class BookingNotFoundError(ValueError):
    pass


class SpaceNotFoundError(ValueError):
    pass


BOOKABLE_HOURS_PER_DAY = Decimal("12")


def get_space(session: Session, space_id: int) -> Space:
    space = session.get(Space, space_id)
    if not space or not space.active:
        raise SpaceNotFoundError("active space not found")
    return space


def get_space_for_update(session: Session, space_id: int) -> Space:
    """Serialize booking creation per space on databases that support row locks.

    PostgreSQL honors SELECT ... FOR UPDATE. SQLite ignores the clause but still
    serializes writes, which is sufficient for this local-development MVP.
    """
    space = session.scalar(
        select(Space)
        .where(Space.id == space_id, Space.active.is_(True))
        .with_for_update()
    )
    if not space:
        raise SpaceNotFoundError("active space not found")
    return space


def has_conflict(
    session: Session,
    space_id: int,
    start: datetime,
    end: datetime,
) -> bool:
    stmt = (
        select(Booking.id)
        .where(
            Booking.space_id == space_id,
            Booking.status == "confirmed",
            Booking.start_time < end,
            Booking.end_time > start,
        )
        .limit(1)
    )
    return session.scalar(stmt) is not None


def _bookings_overlapping(
    session: Session,
    *,
    space_id: int | None,
    start: datetime,
    end: datetime,
) -> list[Booking]:
    conditions = [
        Booking.status == "confirmed",
        Booking.start_time < end,
        Booking.end_time > start,
    ]
    if space_id is not None:
        conditions.append(Booking.space_id == space_id)
    return list(session.scalars(select(Booking).where(*conditions)).all())


def _overlap_hours(booking: Booking, start: datetime, end: datetime) -> Decimal:
    overlap_start = max(booking.start_time, start)
    overlap_end = min(booking.end_time, end)
    seconds = max((overlap_end - overlap_start).total_seconds(), 0)
    return Decimal(str(seconds)) / Decimal("3600")


def occupancy_ratio(
    session: Session,
    space: Space,
    booking_start: datetime,
) -> float:
    local_day = as_local(booking_start, space.timezone_name).date()
    day_start, day_end = local_day_utc_bounds(local_day, space.timezone_name)
    bookings = _bookings_overlapping(
        session,
        space_id=space.id,
        start=day_start,
        end=day_end,
    )
    booked_hours = sum(
        (_overlap_hours(booking, day_start, day_end) for booking in bookings),
        Decimal("0"),
    )
    return min(float(booked_hours / BOOKABLE_HOURS_PER_DAY), 1.0)


def _calculate_quote(
    session: Session,
    space: Space,
    start: datetime,
    end: datetime,
) -> dict[str, int | float | str]:
    hours = Decimal(str((end - start).total_seconds())) / Decimal("3600")
    occupancy = occupancy_ratio(session, space, start)

    if occupancy < 0.5:
        multiplier = Decimal("1.00")
    elif occupancy < 0.8:
        multiplier = Decimal("1.15")
    else:
        multiplier = Decimal("1.35")

    # Weekend is evaluated in the workspace's local timezone, not server time.
    if as_local(start, space.timezone_name).weekday() >= 5:
        multiplier *= Decimal("0.90")

    total = (
        Decimal(space.base_hourly_rate_vnd) * hours * multiplier
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return {
        "space_id": space.id,
        "hours": round(float(hours), 2),
        "occupancy_ratio": round(occupancy, 3),
        "multiplier": round(float(multiplier), 3),
        "total_price_vnd": int(total),
        "currency": "VND",
    }


def price_quote(
    session: Session,
    space_id: int,
    start: datetime,
    end: datetime,
) -> dict[str, int | float | str]:
    return _calculate_quote(session, get_space(session, space_id), start, end)


def create_booking(
    session: Session,
    *,
    space_id: int,
    customer_name: str,
    start: datetime,
    end: datetime,
) -> Booking:
    try:
        # Lock the inventory row before checking availability. This removes the
        # check-then-insert race on PostgreSQL when every booking path follows it.
        space = get_space_for_update(session, space_id)
        if has_conflict(session, space_id, start, end):
            raise BookingConflictError("space is already booked during this interval")

        quote = _calculate_quote(session, space, start, end)
        booking = Booking(
            space_id=space_id,
            customer_name=customer_name,
            start_time=start,
            end_time=end,
            total_price_vnd=int(quote["total_price_vnd"]),
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking
    except Exception:
        session.rollback()
        raise


def cancel_booking(session: Session, booking_id: int) -> Booking:
    booking = session.get(Booking, booking_id)
    if not booking:
        raise BookingNotFoundError("booking not found")
    if booking.status != "cancelled":
        booking.status = "cancelled"
        session.commit()
        session.refresh(booking)
    return booking


def booking_daily_allocation(
    booking: Booking,
    timezone_name: str,
) -> dict[date, int]:
    """Split one booking's total price across every local calendar day it
    touches, so the parts sum EXACTLY to booking.total_price_vnd.

    Why this exists: booking.total_price_vnd is one integer covering the
    whole booking. A booking that crosses local midnight touches two
    different calendar days, and each day's /analytics/daily call used to
    work out its own share independently and round it on its own (HALF_UP).
    Two independent roundings of two halves can each round up, and the day
    totals no longer add back to the original booking total.

    The fix: compute this booking's split across ALL the days it touches in
    one pass. Every day except the last is rounded normally. The last day
    gets whatever is left over (total minus everything already assigned),
    not its own independently-rounded share. That remainder-absorption is
    what guarantees sum(allocation.values()) == booking.total_price_vnd,
    always, by construction, regardless of which days round up or down.
    """
    total_hours = Decimal(str((booking.end_time - booking.start_time).total_seconds())) / Decimal("3600")
    if total_hours <= 0:
        return {}

    # Walk forward from the booking's local start date, one day at a time,
    # stopping the moment a day gets zero overlap hours. This naturally
    # excludes a false "next day" when end_time lands exactly on local
    # midnight (that day would compute to 0 overlap hours and never be
    # added), so there's no separate midnight special-case to get wrong.
    days: list[date] = []
    day = as_local(booking.start_time, timezone_name).date()
    while True:
        day_start, day_end = local_day_utc_bounds(day, timezone_name)
        if _overlap_hours(booking, day_start, day_end) <= 0:
            break
        days.append(day)
        day = date.fromordinal(day.toordinal() + 1)

    allocation: dict[date, int] = {}
    running_total = 0
    for i, d in enumerate(days):
        if i == len(days) - 1:
            # Last day absorbs the remainder instead of rounding its own
            # share. This is the line that makes the total exact.
            allocation[d] = booking.total_price_vnd - running_total
            continue
        day_start, day_end = local_day_utc_bounds(d, timezone_name)
        day_hours = _overlap_hours(booking, day_start, day_end)
        share = (
            Decimal(booking.total_price_vnd) * day_hours / total_hours
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        allocation[d] = int(share)
        running_total += allocation[d]

    return allocation


def daily_analytics(
    session: Session,
    day: date,
    timezone_name: str,
) -> dict[str, int | float | str | date]:
    timezone_name = validate_timezone_name(timezone_name)
    start, end = local_day_utc_bounds(day, timezone_name)
    bookings = _bookings_overlapping(
        session,
        space_id=None,
        start=start,
        end=end,
    )
    hours = sum(
        (_overlap_hours(booking, start, end) for booking in bookings),
        Decimal("0"),
    )
    # Each booking's contribution to *this* day comes from its own full
    # cross-day allocation, not a fraction rounded in isolation. See
    # booking_daily_allocation() for why that distinction is the whole fix.
    revenue = sum(
        booking_daily_allocation(booking, timezone_name).get(day, 0)
        for booking in bookings
    )

    return {
        "day": day,
        "timezone_name": timezone_name,
        "confirmed_bookings": len(bookings),
        "booked_hours": round(float(hours), 2),
        "revenue_vnd": int(revenue),
    }
