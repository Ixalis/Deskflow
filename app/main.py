from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_session
from .models import Booking, Space
from .schemas import (
    AnalyticsRead,
    BookingCancelRead,
    BookingCreate,
    BookingRead,
    QuoteRead,
    QuoteRequest,
    SpaceCreate,
    SpaceRead,
)
from .services import (
    BookingConflictError,
    BookingNotFoundError,
    SpaceNotFoundError,
    cancel_booking,
    create_booking,
    daily_analytics,
    price_quote,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="DeskFlow API",
    version="0.2.0",
    description="Coworking inventory, booking, pricing and analytics MVP",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/spaces", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def add_space(
    payload: SpaceCreate,
    session: Session = Depends(get_session),
) -> Space:
    space = Space(**payload.model_dump())
    session.add(space)
    try:
        session.commit()
        session.refresh(space)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "space name already exists") from exc
    return space


@app.get("/spaces", response_model=list[SpaceRead])
def list_spaces(session: Session = Depends(get_session)) -> list[Space]:
    return list(
        session.scalars(
            select(Space).where(Space.active.is_(True)).order_by(Space.name)
        ).all()
    )


@app.post("/quotes", response_model=QuoteRead)
def quote(
    payload: QuoteRequest,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return price_quote(
            session,
            payload.space_id,
            payload.start_time,
            payload.end_time,
        )
    except SpaceNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/bookings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def book(
    payload: BookingCreate,
    session: Session = Depends(get_session),
) -> Booking:
    try:
        return create_booking(
            session,
            space_id=payload.space_id,
            customer_name=payload.customer_name,
            start=payload.start_time,
            end=payload.end_time,
        )
    except SpaceNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except BookingConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.patch("/bookings/{booking_id}/cancel", response_model=BookingCancelRead)
def cancel(
    booking_id: int,
    session: Session = Depends(get_session),
) -> dict[str, int | str]:
    try:
        booking = cancel_booking(session, booking_id)
    except BookingNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": booking.id, "status": booking.status}


@app.get("/bookings", response_model=list[BookingRead])
def list_bookings(session: Session = Depends(get_session)) -> list[Booking]:
    return list(session.scalars(select(Booking).order_by(Booking.start_time)).all())


@app.get("/analytics/daily", response_model=AnalyticsRead)
def analytics(
    day: date,
    timezone_name: str = Query(default="Asia/Ho_Chi_Minh"),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return daily_analytics(session, day, timezone_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
