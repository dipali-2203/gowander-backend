
from math import asin, cos, isfinite, radians, sin, sqrt, ceil

from app.schemas import (
    AttractionInput,
    ItineraryStop,
    Preferences,
)

from app.services.routing import TravelMatrix, build_travel_time_matrix


def distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate straight-line distance using the Haversine formula."""
    lat1, lon1, lat2, lon2 = map(
        radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    # Protect against floating-point rounding.
    a = min(1.0, max(0.0, a))

    return 6371.0 * 2 * asin(sqrt(a))


def estimate_travel_minutes(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> int:
    """
    Temporary estimate based on straight-line distance.
    Replace this function with a routing-matrix lookup later.
    """
    km = distance_km(lat1, lon1, lat2, lon2)
    return ceil(km / 25.0 * 60.0)


def calculate_attraction_risk(
    attraction: AttractionInput,
) -> float:
    """
    Baseline probability of at least one disruption.
    Assumes independent weather, crowd, and availability risks.
    """
    risks = [
        attraction.weather_risk,
        attraction.crowd_risk,
        attraction.availability_risk,
    ]

    survival = 1.0
    for risk in risks:
        survival *= 1.0 - risk

    return 1.0 - survival


def generate_greedy_itinerary(
    attractions: list[AttractionInput],
    preferences: Preferences,
    start_latitude: float,
    start_longitude: float,
    budget: float,
    available_minutes: int,
    travel_matrix: TravelMatrix | None = None,
) -> dict:
    """Generate a feasible greedy itinerary for one planning day."""

    if len({a.id for a in attractions}) != len(attractions):
        raise ValueError("Attraction IDs must be unique.")

    numbers = [
        start_latitude,
        start_longitude,
        budget,
        float(available_minutes),
    ]

    if not all(isfinite(value) for value in numbers):
        raise ValueError("Planning inputs must be finite numbers.")

    if budget < 0 or available_minutes <= 0:
        raise ValueError(
            "Budget must be non-negative and available time positive."
        )

    # Build a fallback matrix when one is not provided.
    if travel_matrix is None:
        travel_matrix = build_travel_time_matrix(
            start=(start_latitude, start_longitude),
            attractions=attractions,
            provider="haversine",
        )

    expected_size = len(attractions) + 1

    if (
        len(travel_matrix) != expected_size
        or any(len(row) != expected_size for row in travel_matrix)
    ):
        raise ValueError(
            "Travel matrix dimensions do not match locations."
        )

    # Index 0 represents the starting location.
    # Attraction indices correspond to their positions in the matrix.
    attraction_indices = {
        attraction.id: index + 1
        for index, attraction in enumerate(attractions)
    }

    remaining = list(attractions)
    stops: list[ItineraryStop] = []

    current_index = 0
    elapsed = 0
    spent = 0.0

    while remaining:
        candidates = []

        for attraction in remaining:
            attraction_index = attraction_indices[attraction.id]

            travel = travel_matrix[current_index][attraction_index]

            if travel is None:
                continue

            required_minutes = travel + attraction.visit_minutes

            if spent + attraction.cost > budget:
                continue

            if elapsed + required_minutes > available_minutes:
                continue

            category_weight = preferences.interests.get(
                attraction.category.lower(), 0.5
            )

            utility = (
                attraction.preference_score * category_weight
            )

            risk = calculate_attraction_risk(attraction)

            # Risk-averse travelers receive a stronger risk penalty.
            risk_penalty = 1.0 - preferences.risk_tolerance

            risk_adjusted_utility = utility * (
                1.0 - risk * risk_penalty
            )

            score = risk_adjusted_utility / max(
                required_minutes, 1
            )

            candidates.append(
                (
                    score,
                    attraction,
                    travel,
                    risk,
                    attraction_index,
                )
            )

        if not candidates:
            break

        # Deterministic tie-breaking makes baseline tests reproducible.
        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1].id,
            )
        )

        _, selected, travel, risk, selected_index = candidates[0]

        arrival = elapsed + travel
        departure = arrival + selected.visit_minutes

        stops.append(
            ItineraryStop(
                attraction_id=selected.id,
                name=selected.name,
                arrival_minute=arrival,
                departure_minute=departure,
                travel_minutes_before=travel,
                cost=selected.cost,
                preference_score=selected.preference_score,
                risk_score=risk,
            )
        )

        elapsed = departure
        spent += selected.cost
        current_index = selected_index
        remaining.remove(selected)

    total_travel = sum(
        stop.travel_minutes_before for stop in stops
    )

    total_visit = sum(
        stop.departure_minute - stop.arrival_minute
        for stop in stops
    )

    satisfaction = (
        sum(stop.preference_score for stop in stops) / len(stops)
        if stops else 0.0
    )

    trip_survival = 1.0

    for stop in stops:
        trip_survival *= 1.0 - stop.risk_score

    warnings = []

    if not stops:
        warnings.append(
            "No attractions fit the available budget and time."
        )
    elif remaining:
        warnings.append(
            f"{len(remaining)} attractions were omitted because "
            "of budget or time constraints."
        )

    # Feasible means the selected itinerary obeys these hard limits.
    feasible = (
        len(stops) > 0
        and spent <= budget
        and total_travel + total_visit <= available_minutes
    )

    return {
        "stops": stops,
        "total_cost": round(spent, 2),
        "total_travel_minutes": total_travel,
        "total_visit_minutes": total_visit,
        "satisfaction": round(satisfaction, 3),
        "risk_score": round(1.0 - trip_survival, 3),
        "feasible": feasible,
        "warnings": warnings,
    }