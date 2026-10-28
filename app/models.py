
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    destination: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    budget: Mapped[float] = mapped_column(Float)
    available_minutes_per_day: Mapped[int] = mapped_column(Integer)
    start_latitude: Mapped[float] = mapped_column(Float)
    start_longitude: Mapped[float] = mapped_column(Float)
    preferences: Mapped[dict] = mapped_column(JSON)

    latest_itinerary: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class Attraction(Base):
    __tablename__ = "attractions"

    id: Mapped[str] = mapped_column(
        String(100), primary_key=True
    )
    destination: Mapped[str] = mapped_column(
        String(100), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(50))

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    cost: Mapped[float] = mapped_column(Float, default=0.0)
    visit_minutes: Mapped[int] = mapped_column(Integer)

    preference_score: Mapped[float] = mapped_column(Float, default=0.5)
    weather_risk: Mapped[float] = mapped_column(Float, default=0.0)
    crowd_risk: Mapped[float] = mapped_column(Float, default=0.0)
    availability_risk: Mapped[float] = mapped_column(Float, default=0.0)