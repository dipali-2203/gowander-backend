
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Preferences(BaseModel):
    interests: dict[str, float] = Field(
        default_factory=lambda: {"history": 0.8, "food": 0.7}
    )
    risk_tolerance: float = Field(default=0.3, ge=0, le=1)
    walking_tolerance: float = Field(default=0.5, ge=0, le=1)


class TripCreate(BaseModel):
    destination: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date
    budget: float = Field(gt=0)
    available_minutes_per_day: int = Field(default=480, gt=0)
    start_latitude: float = Field(ge=-90, le=90)
    start_longitude: float = Field(ge=-180, le=180)
    preferences: Preferences = Field(default_factory=Preferences)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class AttractionInput(BaseModel):
    id: str
    name: str
    category: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    cost: float = Field(default=0, ge=0)
    visit_minutes: int = Field(gt=0)
    preference_score: float = Field(ge=0, le=1)
    weather_risk: float = Field(default=0.0, ge=0, le=1)
    crowd_risk: float = Field(default=0.0, ge=0, le=1)
    availability_risk: float = Field(default=0.0, ge=0, le=1)


class OptimizeRequest(BaseModel):
    attractions: list[AttractionInput] = Field(min_length=1)
    algorithm: Literal["greedy"] = "greedy"

class ReplanRequest(BaseModel):
    current_latitude: float = Field(ge=-90, le=90)
    current_longitude: float = Field(ge=-180, le=180)

    remaining_budget: float = Field(ge=0)
    remaining_minutes: int = Field(ge=0)

    completed_attraction_ids: list[str] = Field(
        default_factory=list
    )
    closed_attraction_ids: list[str] = Field(
        default_factory=list
    )

class ItineraryStop(BaseModel):
    attraction_id: str
    name: str
    arrival_minute: int
    departure_minute: int
    travel_minutes_before: int
    cost: float
    preference_score: float
    risk_score: float


class ItineraryResponse(BaseModel):
    trip_id: int
    algorithm: str
    stops: list[ItineraryStop]
    total_cost: float
    total_travel_minutes: int
    total_visit_minutes: int
    satisfaction: float
    risk_score: float
    feasible: bool
    warnings: list[str]


class ReplanResponse(ItineraryResponse):
    completed_attraction_ids: list[str] = Field(
        default_factory=list
    )
    excluded_closed_attraction_ids: list[str] = Field(
        default_factory=list
    )