from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .time_utils import to_utc_naive, validate_timezone_name


class SpaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    capacity: int = Field(gt=0, le=200)
    base_hourly_rate_vnd: int = Field(gt=0, le=100_000_000)
    timezone_name: str = "Asia/Ho_Chi_Minh"

    @field_validator("timezone_name")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return validate_timezone_name(value)


class SpaceRead(SpaceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    active: bool


class QuoteRequest(BaseModel):
    space_id: int
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def normalize_to_utc(cls, value: datetime) -> datetime:
        return to_utc_naive(value)

    @model_validator(mode="after")
    def valid_interval(self) -> "QuoteRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if (self.end_time - self.start_time).total_seconds() > 12 * 3600:
            raise ValueError("bookings may not exceed 12 hours")
        return self


class QuoteRead(BaseModel):
    space_id: int
    hours: float
    occupancy_ratio: float
    multiplier: float
    total_price_vnd: int
    currency: str = "VND"


class BookingCreate(QuoteRequest):
    customer_name: str = Field(min_length=2, max_length=120)


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    space_id: int
    customer_name: str
    start_time: datetime
    end_time: datetime
    total_price_vnd: int
    status: str


class BookingCancelRead(BaseModel):
    id: int
    status: str


class AnalyticsRead(BaseModel):
    day: date
    timezone_name: str
    confirmed_bookings: int
    booked_hours: float
    revenue_vnd: int
