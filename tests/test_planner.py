
from app.schemas import AttractionInput, Preferences
from app.services.planner import generate_greedy_itinerary


import pytest

from app.schemas import AttractionInput, Preferences
from app.services.planner import (
    calculate_attraction_risk,
    generate_greedy_itinerary,
)


def make_attraction(
    attraction_id: str,
    *,
    cost: float = 100,
    risk: float = 0.0,
) -> AttractionInput:
    return AttractionInput(
        id=attraction_id,
        name=f"Place {attraction_id}",
        category="history",
        latitude=17.385,
        longitude=78.4867,
        cost=cost,
        visit_minutes=60,
        preference_score=0.9,
        weather_risk=risk,
        crowd_risk=0.0,
        availability_risk=0.0,
    )


def test_duplicate_attraction_ids_are_rejected():
    attraction = make_attraction("museum")

    with pytest.raises(ValueError, match="unique"):
        generate_greedy_itinerary(
            attractions=[attraction, attraction],
            preferences=Preferences(),
            start_latitude=17.385,
            start_longitude=78.4867,
            budget=1000,
            available_minutes=240,
        )


def test_no_feasible_attractions_returns_warning():
    result = generate_greedy_itinerary(
        attractions=[make_attraction("expensive", cost=5000)],
        preferences=Preferences(),
        start_latitude=17.385,
        start_longitude=78.4867,
        budget=100,
        available_minutes=240,
    )

    assert result["stops"] == []
    assert result["feasible"] is False
    assert result["total_cost"] == 0
    assert result["warnings"]


def test_attraction_risk_calculation():
    attraction = make_attraction("museum", risk=0.2)

    risk = calculate_attraction_risk(attraction)

    assert risk == pytest.approx(0.2)


def test_planner_respects_budget():
    attractions = [
        AttractionInput(
            id="expensive",
            name="Expensive Attraction",
            category="history",
            latitude=17.38,
            longitude=78.48,
            cost=5000,
            visit_minutes=60,
            preference_score=1.0,
        ),
        AttractionInput(
            id="affordable",
            name="Affordable Attraction",
            category="history",
            latitude=17.39,
            longitude=78.49,
            cost=100,
            visit_minutes=60,
            preference_score=0.9,
        ),
    ]

    result = generate_greedy_itinerary(
        attractions=attractions,
        preferences=Preferences(
            interests={"history": 1.0},
            risk_tolerance=0.2,
            walking_tolerance=0.5,
        ),
        start_latitude=17.385,
        start_longitude=78.4867,
        budget=200,
        available_minutes=240,
    )

    assert result["total_cost"] <= 200
    assert all(stop.cost <= 200 for stop in result["stops"])
    assert all(stop.arrival_minute >= 0 for stop in result["stops"])
