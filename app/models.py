from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .time_utils import utc_now_naive


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    base_hourly_rate_vnd: Mapped[int] = mapped_column(Integer)
    timezone_name: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    bookings: Mapped[list["Booking"]] = relationship(back_populates="space")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    # Stored as naive UTC. API inputs must include an offset and are normalized.
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    total_price_vnd: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    space: Mapped[Space] = relationship(back_populates="bookings")
