from __future__ import annotations

from datetime import datetime, timedelta, timezone

VN = timezone(timedelta(hours=7))


def iso(value: datetime) -> str:
    return value.isoformat()


def create_space(client, *, name: str = "Focus Room", rate: int = 100_000) -> int:
    response = client.post(
        "/spaces",
        json={
            "name": name,
            "capacity": 4,
            "base_hourly_rate_vnd": rate,
            "timezone_name": "Asia/Ho_Chi_Minh",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def booking_payload(space_id: int, start: datetime, end: datetime, name: str = "Lan Nguyen") -> dict:
    return {
        "space_id": space_id,
        "customer_name": name,
        "start_time": iso(start),
        "end_time": iso(end),
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_cors_allows_vite_origin(client):
    response = client.options(
        "/spaces",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_duplicate_space_name_returns_conflict(client):
    create_space(client)
    response = client.post(
        "/spaces",
        json={
            "name": "Focus Room",
            "capacity": 8,
            "base_hourly_rate_vnd": 120_000,
        },
    )
    assert response.status_code == 409


def test_timezone_offset_is_normalized_before_conflict_check(client):
    space_id = create_space(client)
    first_start = datetime(2026, 7, 21, 9, 0, tzinfo=VN)
    first_end = first_start + timedelta(hours=1)
    assert client.post(
        "/bookings",
        json=booking_payload(space_id, first_start, first_end),
    ).status_code == 201

    # 03:30 UTC is 10:30 in Vietnam, so this starts after the first booking.
    second_start = datetime(2026, 7, 21, 3, 30, tzinfo=timezone.utc)
    second_end = second_start + timedelta(hours=1)
    response = client.post(
        "/bookings",
        json=booking_payload(space_id, second_start, second_end, "Minh Tran"),
    )
    assert response.status_code == 201, response.text


def test_naive_datetime_is_rejected(client):
    space_id = create_space(client)
    response = client.post(
        "/quotes",
        json={
            "space_id": space_id,
            "start_time": "2026-07-21T09:00:00",
            "end_time": "2026-07-21T10:00:00",
        },
    )
    assert response.status_code == 422
    assert "timezone offset" in response.text


def test_back_to_back_bookings_are_allowed(client):
    space_id = create_space(client)
    start = datetime(2026, 7, 21, 9, 0, tzinfo=VN)
    middle = start + timedelta(hours=1)
    end = middle + timedelta(hours=1)
    assert client.post(
        "/bookings", json=booking_payload(space_id, start, middle)
    ).status_code == 201
    assert client.post(
        "/bookings", json=booking_payload(space_id, middle, end, "Minh Tran")
    ).status_code == 201


def test_overlapping_booking_returns_conflict(client):
    space_id = create_space(client)
    start = datetime(2026, 7, 21, 9, 0, tzinfo=VN)
    end = start + timedelta(hours=2)
    assert client.post(
        "/bookings", json=booking_payload(space_id, start, end)
    ).status_code == 201
    response = client.post(
        "/bookings",
        json=booking_payload(
            space_id,
            start + timedelta(minutes=30),
            end,
            "Minh Tran",
        ),
    )
    assert response.status_code == 409


def test_weekend_discount_uses_space_local_time(client):
    space_id = create_space(client)
    # Saturday morning in Vietnam, still Friday in part of UTC.
    start = datetime(2026, 7, 25, 0, 30, tzinfo=VN)
    end = start + timedelta(hours=2)
    response = client.post(
        "/quotes",
        json={"space_id": space_id, "start_time": iso(start), "end_time": iso(end)},
    )
    assert response.status_code == 200
    assert response.json()["multiplier"] == 0.9
    assert response.json()["total_price_vnd"] == 180_000
    assert isinstance(response.json()["total_price_vnd"], int)


def test_occupancy_pricing_tier(client):
    space_id = create_space(client)
    start = datetime(2026, 7, 24, 8, 0, tzinfo=VN)
    end = start + timedelta(hours=6)
    assert client.post(
        "/bookings", json=booking_payload(space_id, start, end)
    ).status_code == 201

    quote_start = datetime(2026, 7, 24, 15, 0, tzinfo=VN)
    response = client.post(
        "/quotes",
        json={
            "space_id": space_id,
            "start_time": iso(quote_start),
            "end_time": iso(quote_start + timedelta(hours=1)),
        },
    )
    assert response.status_code == 200
    assert response.json()["occupancy_ratio"] == 0.5
    assert response.json()["multiplier"] == 1.15
    assert response.json()["total_price_vnd"] == 115_000


def test_booking_may_not_exceed_twelve_hours(client):
    space_id = create_space(client)
    start = datetime(2026, 7, 21, 6, 0, tzinfo=VN)
    response = client.post(
        "/quotes",
        json={
            "space_id": space_id,
            "start_time": iso(start),
            "end_time": iso(start + timedelta(hours=13)),
        },
    )
    assert response.status_code == 422


def test_missing_space_returns_not_found(client):
    start = datetime(2026, 7, 21, 9, 0, tzinfo=VN)
    response = client.post(
        "/quotes",
        json={
            "space_id": 999,
            "start_time": iso(start),
            "end_time": iso(start + timedelta(hours=1)),
        },
    )
    assert response.status_code == 404


def test_cancellation_releases_the_interval(client):
    space_id = create_space(client)
    start = datetime(2026, 7, 21, 9, 0, tzinfo=VN)
    end = start + timedelta(hours=2)
    created = client.post(
        "/bookings", json=booking_payload(space_id, start, end)
    )
    booking_id = created.json()["id"]
    cancelled = client.patch(f"/bookings/{booking_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(
        "/bookings", json=booking_payload(space_id, start, end, "Minh Tran")
    ).status_code == 201


def test_daily_analytics_uses_requested_local_day(client):
    space_id = create_space(client)
    start = datetime(2026, 7, 22, 23, 0, tzinfo=VN)
    end = start + timedelta(hours=2)
    client.post("/bookings", json=booking_payload(space_id, start, end))

    response = client.get(
        "/analytics/daily",
        params={"day": "2026-07-22", "timezone_name": "Asia/Ho_Chi_Minh"},
    )
    assert response.status_code == 200
    assert response.json()["confirmed_bookings"] == 1
    assert response.json()["booked_hours"] == 1.0
    assert response.json()["revenue_vnd"] == 100_000
